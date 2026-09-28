# === src/worker/main.py — DECOUPLED IO + CPU WORKERS ===
"""Worker main loop — tách biệt hoàn toàn I/O worker và CPU worker.

Kiến trúc:
    IO Worker  (WORKER_ROLE=io):
        - Kéo job status=PENDING từ DB
        - Chạy Stage 1 (Claude) + Stage 2∥3 (Fal + Vbee) song song
        - Khi xong → push job_id vào Redis render queue
        - KHÔNG bao giờ chạy MoviePy

    CPU Worker (WORKER_ROLE=cpu):
        - BRPOP từ Redis render queue (block, không poll DB)
        - Chỉ chạy Stage 4 (MoviePy render) trong PROCESS RIÊNG
          (có thể kill cứng khi timeout, không để zombie ăn CPU)
        - Global semaphore qua Redis: max GLOBAL_RENDER_SLOTS render/VPS

Flow:
    API → DB (PENDING)
        → IO worker kéo → Stage 1,2,3 → LPUSH render_queue
                                       → CPU worker BRPOP → Stage 4 → COMPLETED
"""
from __future__ import annotations

import asyncio
import multiprocessing as mp
import os
import signal
import socket
import types
import uuid
from pathlib import Path
from typing import Any, Final

import redis.asyncio as aioredis

from src.worker.cleanup import cleanup_loop
from src.core.database.schemas import RenderJobStatus
from src.core.images.fal_image_engine import FalImageEngine
from src.core.moviepy.video_engine import render_final_video
from src.core.scripts.claude_engine import ClaudeEngine
from src.config import settings
from src.core.voice.audio_step import generate_audio_step
from src.worker.redis_client import get_redis
from src.worker.db_helpers import (
    fetch_and_lock_job,
    fetch_job_by_id,
    finalize_job_atomic,
    load_metadata_db,
    save_metadata_db,
    update_scene_field,
    update_job_status,
)
from src.utils.file_manager import create_job_folder
from src.utils.logger import get_logger
from src.utils.path_utils import safe_exists, safe_resolve
from src.core.animation.animation_pipeline import run_animation_pipeline
from src.worker.redis_semaphore import (
    acquire_render_slot, 
    acquire_fal_slot,
    GLOBAL_RENDER_SLOTS
)

logger = get_logger(__name__)

# ─── Identity ─────────────────────────────────────────────────────────────────
WORKER_ID:   Final[str] = f"worker-{socket.gethostname()}-{uuid.uuid4().hex[:6]}"
WORKER_ROLE: Final[str] = os.getenv("WORKER_ROLE", "io")  # io | cpu | primary

# ─── Redis render queue ───────────────────────────────────────────────────────
RENDER_QUEUE_KEY:          Final[str] = "worker:render_queue"
RENDER_QUEUE_BRPOP_TIMEOUT: Final[int] = 5  

# ─── Concurrency theo role ────────────────────────────────────────────────────
_CONCURRENCY_MAP: Final[dict[str, int]] = {
    "io":      5,  
    "cpu":     1,  
    "primary": 2,
}
MAX_CONCURRENT_JOBS: Final[int] = _CONCURRENCY_MAP.get(WORKER_ROLE, 3)

# ─── Timeout (dynamic theo độ dài video + số scene) ───────────────────────────

# Stage 4 — render
RENDER_BASE_OVERHEAD_S:  Final[float] = 30.0    # load assets + mux cuối, không đổi theo duration
RENDER_RATIO_WORST_CASE: Final[float] = 4.0     # 120s render / 60s video (theo system_knowledge)
RENDER_SAFETY_MARGIN:    Final[float] = 1.5     # buffer 50% cho VPS load dao động

MAX_VIDEO_DURATION_S:    Final[float] = 10 * 60 # 10 phút — max sản phẩm cho phép


RENDER_TIMEOUT_MIN_S: Final[float] = 180.0      # sàn 3 phút

RENDER_TIMEOUT_MAX_S: Final[float] = (        
    RENDER_BASE_OVERHEAD_S
    + MAX_VIDEO_DURATION_S * RENDER_RATIO_WORST_CASE * RENDER_SAFETY_MARGIN
    + 300                                    
)

# Đây CHỈ là lớp phòng hộ thứ 2 — lớp kill thật nằm trong _run_render_in_process.
RENDER_KILL_GRACE_S: Final[float] = 30.0

# Stage 1-3 — IO (Claude + fal.ai + Vbee), tỉ lệ theo số scene
IO_BASE_OVERHEAD_S: Final[float] = 60.0         # Stage 1: script generation
IO_PER_SCENE_S: Final[float] = 15.0         

IO_TIMEOUT_MIN_S: Final[float] = 600.0
IO_TIMEOUT_MAX_S: Final[float] = 1800.0

# ─── Quality gate ─────────────────────────────────────────────────────────────
_SCENES_VALIDITY_THRESHOLD: Final[float] = 0.9

# ─── Defaults ─────────────────────────────────────────────────────────────────
_DEFAULT_TOPIC          = "Chủ đề ngẫu nhiên"
_DEFAULT_MINUTES        = 0.5
_DEFAULT_TONE           = "genz_meme"
_DEFAULT_LANGUAGE       = "vi"
_DEFAULT_STRUCTURE      = "hook_twist"
_DEFAULT_PACE           = "balanced"
_DEFAULT_MAIN_CHARACTER = "a stickman wearing a tie and round glasses"
_DEFAULT_VOICE_CODE     = "hn_female_ngochuyen_full_48k-fhg"
_DEFAULT_USE_BEST_MODEL = False
_DEFAULT_USE_COLOR_IMAGE = False

# ─── State ────────────────────────────────────────────────────────────────────
_job_semaphore  = asyncio.Semaphore(MAX_CONCURRENT_JOBS)
_active_tasks:  set[asyncio.Task] = set()
_shutdown_event = asyncio.Event()

# ══════════════════════════════════════════════════════════════════════════════
# STAGE FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

async def generate_script_step(
    job_id: str, topic: str, minutes: float, tone: str,
    language: str, structure: str, pace: str,
    main_character: str, use_best_model: bool, 
    use_color_image: bool,
) -> bool:
    logger.info("stage1.start", extra={"job_id": job_id, "topic": topic})
    try:
        async with ClaudeEngine() as engine:
            script_data = await engine.generate_video_script(
                topic=topic, minutes=minutes, tone=tone,
                language=language, story_structure=structure,
                pace=pace, main_character=main_character,
                use_best_model=use_best_model,
                use_color_image=use_color_image,
            )
    except Exception as exc:
        logger.error("stage1.crashed", extra={"job_id": job_id, "error": str(exc)}, exc_info=True)
        return False

    if not script_data or not script_data.get("scenes"):
        logger.error("stage1.empty_scenes", extra={"job_id": job_id})
        return False

    current = await load_metadata_db(job_id) or {}
    current.update(script_data)
    await save_metadata_db(job_id, current)
    logger.info("stage1.ok", extra={"job_id": job_id, "scenes": len(script_data["scenes"])})
    return True


async def render_images_step(job_id: str, images_dir: Path, use_best_model: bool) -> None:
    async with acquire_fal_slot(get_redis(), job_id):
        data = await load_metadata_db(job_id)
        if not data or "scenes" not in data:
            return
        images_dir.mkdir(parents=True, exist_ok=True)

        async def on_done(scene_idx: int, result: Any) -> None:
            try:
                await update_scene_field(
                    job_id=job_id, scene_idx=scene_idx, kind="image",
                    status_value="completed" if result.success else "failed",
                    path_value=str(result.saved_path) if result.success and result.saved_path else "",
                )
            except Exception as exc:
                logger.error("stage2.callback.failed",
                            extra={"job_id": job_id, "scene_idx": scene_idx, "error": str(exc)})

        async with FalImageEngine() as engine:
            await engine.generate_images_for_script(
                scenes=data["scenes"], images_dir=images_dir,
                delay_seconds=3.0,  use_best_model=use_best_model,
                on_scene_done=on_done,
            )


def _filter_valid_scenes(scenes: list[dict], job_id: str) -> list[dict]:
    valid = []
    for s in scenes:
        paths  = s.get("paths",  {})
        status = s.get("status", {})
        if (status.get("image") == "completed" and
                status.get("audio") == "completed" and
                safe_exists(paths.get("image", "")) and
                safe_exists(paths.get("audio", ""))):
            valid.append(s)
        else:
            logger.warning("stage4.scene.invalid",
                           extra={"job_id": job_id, "scene_id": s.get("scene_id", "?")})
    return valid


# ══════════════════════════════════════════════════════════════════════════════
# RENDER TRONG PROCESS RIÊNG — cho phép kill cứng khi timeout
# ══════════════════════════════════════════════════════════════════════════════

def _render_worker_entry(
    scenes: list[dict],
    final_path: str,
    target_seconds_per_scene: float | None,
    max_seconds_per_scene: float | None,
    result_queue: "mp.Queue",
) -> None:
    """Entry point chạy trong PROCESS CON. Không dùng asyncio ở đây."""
    try:
        success = render_final_video(
            scenes, Path(final_path),
            target_seconds_per_scene=target_seconds_per_scene,
            max_seconds_per_scene=max_seconds_per_scene,
        )
        result_queue.put(("ok", success))
    except Exception as exc:  # phải bắt mọi lỗi để không treo result_queue
        result_queue.put(("error", str(exc)))


async def _run_render_in_process(
    scenes: list[dict],
    final_path: Path,
    target_seconds_per_scene: float | None,
    max_seconds_per_scene: float | None,
    timeout_s: float,
) -> bool:
    """
    Render trong process con. Nếu vượt timeout_s -> kill cứng process đó,
    giải phóng CPU ngay (không zombie như asyncio.to_thread).
    """
    result_queue: mp.Queue = mp.Queue()
    proc = mp.Process(
        target=_render_worker_entry,
        args=(scenes, str(final_path), target_seconds_per_scene, max_seconds_per_scene, result_queue),
        daemon=True,
    )
    proc.start()

    loop = asyncio.get_running_loop()
    # proc.join() là lệnh blocking đồng bộ -> chạy trong thread executor để không khoá event loop.
    # Nhưng vì đây chỉ là JOIN (chờ), không phải code CPU nặng, nên không có vấn đề "zombie thread".
    await loop.run_in_executor(None, proc.join, timeout_s)

    if proc.is_alive():
        logger.warning("render_process.kill", extra={"timeout_s": timeout_s, "pid": proc.pid})
        proc.terminate()           # SIGTERM
        proc.join(timeout=5)
        if proc.is_alive():
            proc.kill()             # SIGKILL cứng nếu terminate không ăn
            proc.join()
        raise asyncio.TimeoutError(f"Render process bị kill sau {timeout_s:.0f}s")

    if result_queue.empty():
        raise RuntimeError(
            f"Render process (pid={proc.pid}) kết thúc bất thường, exitcode={proc.exitcode}"
        )

    status, payload = result_queue.get()
    if status == "error":
        raise RuntimeError(payload)
    return bool(payload)


async def render_video_step(
    job_id: str, video_dir: Path, job_folder_name: str, timeout_s: float,
) -> str:
    data = await load_metadata_db(job_id)
    if not data or "scenes" not in data:
        raise RuntimeError("Không có dữ liệu kịch bản.")

    video_dir.mkdir(parents=True, exist_ok=True)
    final_path = video_dir / f"{job_folder_name}_final.mp4"
    meta = data.get("meta_data", {})

    valid_scenes = await asyncio.to_thread(_filter_valid_scenes, data["scenes"], job_id)
    total = len(data["scenes"])
    valid = len(valid_scenes)
    ratio = (valid / total) if total > 0 else 0.0

    if ratio < _SCENES_VALIDITY_THRESHOLD:
        raise RuntimeError(f"Chỉ {valid}/{total} cảnh hợp lệ ({ratio:.0%}).")

    success = await _run_render_in_process(
        scenes=valid_scenes,
        final_path=final_path,
        target_seconds_per_scene=meta.get("target_seconds_per_scene"),
        max_seconds_per_scene=meta.get("max_seconds_per_scene"),
        timeout_s=timeout_s,
    )
    if not success:
        raise RuntimeError("MoviePy render thất bại.")

    relative = final_path.as_posix().lstrip("/")
    return f"{settings.CLIENT_URL.rstrip('/')}/{relative}"


# ══════════════════════════════════════════════════════════════════════════════
# IO WORKFLOW — Stage 1→3, push render queue
# ══════════════════════════════════════════════════════════════════════════════
def _calculate_io_timeout(scene_count: int) -> float:
    raw = IO_BASE_OVERHEAD_S + (scene_count * IO_PER_SCENE_S)
    return max(IO_TIMEOUT_MIN_S, min(raw, IO_TIMEOUT_MAX_S))

async def process_io_task(job_id: str, config: dict[str, Any]) -> None:
    """Chạy Stage 1-3. Khi xong push job_id vào Redis render queue."""
    topic          = config.get("topic")           or _DEFAULT_TOPIC
    minutes        = config.get("minutes")         or _DEFAULT_MINUTES
    tone           = config.get("tone")            or _DEFAULT_TONE
    language       = config.get("language")        or _DEFAULT_LANGUAGE
    structure      = config.get("story_structure") or _DEFAULT_STRUCTURE
    pace           = config.get("pace")            or _DEFAULT_PACE
    voice_code     = config.get("voice_code")      or _DEFAULT_VOICE_CODE
    use_best_model = config.get("use_best_model")  or _DEFAULT_USE_BEST_MODEL
    use_color_image = config.get("use_color_image") or _DEFAULT_USE_COLOR_IMAGE

    _mc_raw = config.get("main_character") or _DEFAULT_MAIN_CHARACTER
    main_character = (
        _mc_raw.get("description") or _DEFAULT_MAIN_CHARACTER
        if isinstance(_mc_raw, dict) else str(_mc_raw)
    )

    job_path_str, job_folder_name = create_job_folder()
    job_path = Path(job_path_str).resolve()

    # Lưu path để cpu worker biết sau này
    meta = await load_metadata_db(job_id) or {}
    meta["_job_folder_name"] = job_folder_name
    meta["_job_path"]        = str(job_path)
    await save_metadata_db(job_id, meta)

    # Stage 1: Script
    ok = await generate_script_step(
        job_id=job_id, topic=topic, minutes=minutes, tone=tone,
        language=language, structure=structure, pace=pace,
        main_character=main_character, use_best_model=use_best_model,
        use_color_image=use_color_image
    )
    if not ok:
        raise RuntimeError("Stage 1 (Script) thất bại.")

    # Stage 2 + 3: song song
    async with asyncio.TaskGroup() as tg:
        tg.create_task(render_images_step(job_id, job_path / "images", use_best_model=use_best_model),
                       name=f"stage2_{job_id}")
        tg.create_task(generate_audio_step(job_id, job_path / "audios", voice_code),
                       name=f"stage3_{job_id}")

    # Push vào render queue
    await update_job_status(job_id, RenderJobStatus.RENDER_QUEUED)
    await get_redis().lpush(RENDER_QUEUE_KEY, str(job_id))
    logger.info("io_task.done", extra={"job_id": job_id})

async def process_io_job(job: dict[str, Any]) -> None:
    job_id       = job["id"]
    user_id      = job["user_id"]
    cost_credits = job["cost_credits"]
    scene_count  = job["scenes_count"]
    timeout_s    = _calculate_io_timeout(scene_count)
    logger.info("io_job.start", extra={"job_id": job_id})
    try:
        await asyncio.wait_for(
            process_io_task(job_id, job["render_config"]),
            timeout=timeout_s,
        )
    except asyncio.TimeoutError:
        logger.error("io_job.timeout", extra={"job_id": job_id})
        await finalize_job_atomic(job_id=job_id, status=RenderJobStatus.FAILED,
                                  error_msg=f"IO timeout {timeout_s:.0f}s",
                                  refund_user_id=user_id, refund_amount=cost_credits)
    except Exception as exc:
        logger.error("io_job.crashed", extra={"job_id": job_id, "error": str(exc)}, exc_info=True)
        await finalize_job_atomic(job_id=job_id, status=RenderJobStatus.FAILED,
                                  error_msg=str(exc)[:500],
                                  refund_user_id=user_id, refund_amount=cost_credits)

# ══════════════════════════════════════════════════════════════════════════════
# CPU WORKFLOW — Stage 4 only
# ══════════════════════════════════════════════════════════════════════════════
def _calculate_render_timeout(video_duration_seconds: float, scene_count: int) -> float:

    encode_time  = RENDER_BASE_OVERHEAD_S + (
        video_duration_seconds * RENDER_RATIO_WORST_CASE * RENDER_SAFETY_MARGIN
    )
    raw = encode_time * scene_count
    return max(RENDER_TIMEOUT_MIN_S, min(raw, RENDER_TIMEOUT_MAX_S))


async def _execute_render(job_id: str, timeout_s: float) -> str:
    """Chỉ chứa render work — không có semaphore, gọi sau khi slot đã acquired."""
    meta            = await load_metadata_db(job_id) or {}
    job_path        = Path(meta.get("_job_path", ""))
    job_folder_name = meta.get("_job_folder_name", job_id)

    if not job_path or not job_path.exists():
        raise RuntimeError(f"Job path không tồn tại: {job_path}")

    logger.info("stage4.start", extra={"job_id": job_id})
    return await render_video_step(
        job_id=job_id,
        video_dir=job_path / "video",
        job_folder_name=job_folder_name,
        timeout_s=timeout_s,
    )

async def process_cpu_job(job_id: str) -> None:
    job = await fetch_job_by_id(job_id)
    if not job:
        logger.error("cpu_job.not_found", extra={"job_id": job_id})
        return

    user_id      = job["user_id"]
    cost_credits = job["cost_credits"]
    duration_s   = job["duration_seconds"]
    scene_count  = job["scenes_count"]
    timeout_s    = _calculate_render_timeout(duration_s, scene_count)

    logger.info("cpu_job.start", extra={
        "job_id": job_id,
        "duration_s": duration_s,
        "scene_count": scene_count,
        "timeout_s": timeout_s,
    })
    await update_job_status(job_id, RenderJobStatus.PROCESSING)

    try:
        async with acquire_render_slot(get_redis(), job_id):
            logger.info("cpu_job.slot_acquired", extra={"job_id": job_id})

            output_url = await asyncio.wait_for(
                _execute_render(job_id, timeout_s),
                timeout=timeout_s + RENDER_KILL_GRACE_S,
            )

        await finalize_job_atomic(
            job_id=job_id,
            status=RenderJobStatus.COMPLETED,
            output_url=output_url,
        )
        logger.info("cpu_job.done", extra={"job_id": job_id})

    except asyncio.TimeoutError:
        logger.error("cpu_job.timeout", extra={
            "job_id": job_id,
            "timeout_s": timeout_s,
        })
        await finalize_job_atomic(
            job_id=job_id, status=RenderJobStatus.FAILED,
            error_msg=f"Render timeout {timeout_s:.0f}s",
            refund_user_id=user_id, refund_amount=cost_credits,
        )

    except Exception as exc:
        logger.error("cpu_job.crashed",
                     extra={"job_id": job_id, "error": str(exc)}, exc_info=True)
        await finalize_job_atomic(
            job_id=job_id, status=RenderJobStatus.FAILED,
            error_msg=str(exc)[:500],
            refund_user_id=user_id, refund_amount=cost_credits,
        )
# ══════════════════════════════════════════════════════════════════════════════
# WORKER LOOPS
# ══════════════════════════════════════════════════════════════════════════════

async def io_worker_loop() -> None:
    """Kéo PENDING job từ DB, chạy Stage 1-3, push render queue."""
    logger.info("worker.io.start",
                extra={"worker_id": WORKER_ID, "concurrency": MAX_CONCURRENT_JOBS})

    while not _shutdown_event.is_set():
        try:
            acq   = asyncio.create_task(_job_semaphore.acquire())
            sd    = asyncio.create_task(_shutdown_event.wait())
            done, pending = await asyncio.wait({acq, sd}, return_when=asyncio.FIRST_COMPLETED)
            for t in pending:
                t.cancel()

            if _shutdown_event.is_set():
                if acq in done:
                    _job_semaphore.release()
                break

            try:
                job = await fetch_and_lock_job(WORKER_ID)
            except Exception as exc:
                _job_semaphore.release()
                logger.error("io_worker.fetch_failed", extra={"error": str(exc)}, exc_info=True)
                await asyncio.sleep(5.0)
                continue

            if job is None:
                _job_semaphore.release()
                await asyncio.sleep(2.0)
                continue

            async def _run_io(j=job):
                try:
                    await process_io_job(j)
                finally:
                    _job_semaphore.release()

            task = asyncio.create_task(_run_io(), name=f"io_{job['id']}")
            _active_tasks.add(task)
            task.add_done_callback(_active_tasks.discard)

        except Exception as exc:
            logger.error("io_worker.loop_error", extra={"error": str(exc)}, exc_info=True)
            await asyncio.sleep(5.0)


async def cpu_worker_loop() -> None:
    """BRPOP từ Redis render queue, chạy Stage 4."""
    redis = get_redis()
    logger.info("worker.cpu.start",
                extra={"worker_id": WORKER_ID, "queue": RENDER_QUEUE_KEY,
                       "global_slots": GLOBAL_RENDER_SLOTS})

    while not _shutdown_event.is_set():
        try:
            result = await redis.brpop(RENDER_QUEUE_KEY, timeout=RENDER_QUEUE_BRPOP_TIMEOUT)
            if result is None:
                continue 

            _, job_id = result
            logger.info("cpu_worker.received", extra={"job_id": job_id})

            await _job_semaphore.acquire()

            async def _run_cpu(jid=job_id):
                try:
                    await process_cpu_job(jid)
                finally:
                    _job_semaphore.release()

            task = asyncio.create_task(_run_cpu(), name=f"cpu_{job_id}")
            _active_tasks.add(task)
            task.add_done_callback(_active_tasks.discard)

        except aioredis.RedisError as exc:
            logger.error("cpu_worker.redis_error", extra={"error": str(exc)}, exc_info=True)
            await asyncio.sleep(5.0)
        except Exception as exc:
            logger.error("cpu_worker.loop_error", extra={"error": str(exc)}, exc_info=True)
            await asyncio.sleep(5.0)


# ══════════════════════════════════════════════════════════════════════════════
# ANIMATION WORKFLOW (BETA)
# ══════════════════════════════════════════════════════════════════════════════

async def run_animation_workflow(job_id: str, config: dict[str, Any]) -> str:
    job_path_str, _ = create_job_folder()
    job_path = Path(job_path_str).resolve()
    normalized = {
        "topic": _DEFAULT_TOPIC, "tone": _DEFAULT_TONE,
        "language": _DEFAULT_LANGUAGE, "story_structure": _DEFAULT_STRUCTURE,
        "pace": _DEFAULT_PACE, "voice_code": _DEFAULT_VOICE_CODE, **config,
    }
    job    = types.SimpleNamespace(id=job_id, topic=normalized["topic"],
                                   render_config=normalized, output_dir=str(job_path))
    result = await run_animation_pipeline(job)
    return f"{settings.CLIENT_URL.rstrip('/')}/{Path(result.mp4_path).as_posix().lstrip('/')}"


# ══════════════════════════════════════════════════════════════════════════════
# SHUTDOWN + MAIN
# ══════════════════════════════════════════════════════════════════════════════

SHUTDOWN_DRAIN_TIMEOUT: Final[float] = 60.0

def _install_signal_handlers(loop: asyncio.AbstractEventLoop) -> None:
    def _shutdown():
        logger.info("worker.shutdown.requested")
        _shutdown_event.set()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _shutdown)
        except NotImplementedError:
            signal.signal(sig, lambda *_: _shutdown())


async def worker_loop() -> None:
    is_primary   = WORKER_ROLE == "primary"
    cleanup_task = None

    if is_primary:
        cleanup_task = asyncio.create_task(cleanup_loop(), name="cleanup_loop")

    # Rẽ nhánh thật sự theo WORKER_ROLE
    if WORKER_ROLE == "cpu":
        main_task = asyncio.create_task(cpu_worker_loop(), name="cpu_loop")
    else:
        main_task = asyncio.create_task(io_worker_loop(), name="io_loop")

    logger.info("worker.started", extra={"role": WORKER_ROLE, "worker_id": WORKER_ID,
                                          "concurrency": MAX_CONCURRENT_JOBS})
    try:
        await asyncio.gather(main_task, return_exceptions=True)
    finally:
        if _active_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*_active_tasks, return_exceptions=True),
                    timeout=SHUTDOWN_DRAIN_TIMEOUT,
                )
            except asyncio.TimeoutError:
                logger.warning("worker.drain.timeout")

        if cleanup_task:
            cleanup_task.cancel()
            try:
                await cleanup_task
            except asyncio.CancelledError:
                pass

    logger.info("worker.stopped", extra={"role": WORKER_ROLE})


def main() -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    _install_signal_handlers(loop)
    try:
        loop.run_until_complete(worker_loop())
    finally:
        loop.close()


if __name__ == "__main__":
    main()