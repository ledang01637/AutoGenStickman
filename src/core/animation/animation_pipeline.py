"""
animation_pipeline.py — Orchestrate pipeline animation end-to-end

Flow:
  run_animation_pipeline(job)
    ├─ Stage 1: ClaudeAnimationEngine → animation JSON
    ├─ Stage 2 ∥ Stage 3 (parallel):
    │   ├─ Stage 2: Vbee TTS → audio files per scene
    │   └─ Stage 3: StickmanAnimationEngine → mp4 (no audio)
    └─ Stage 4: ffmpeg mux video + audio → final mp4

Dùng từ worker:
    from src.core.animation.animation_pipeline import run_animation_pipeline

    if render_type == "animation":
        result = await run_animation_pipeline(job)
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import tempfile
import time
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .claude_animation_engine import ClaudeAnimationEngine, merge_animation_defaults
from .stickman_animation_engine import StickmanAnimationEngine
from .validators import ValidationError



logger = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────

OUTPUT_BASE  = os.getenv("ANIMATION_OUTPUT_DIR", "/app/jobs")
MAX_RETRIES  = int(os.getenv("ANIMATION_MAX_RETRIES", "1"))

_DEFAULT_VOICE_CODE = "hn_female_ngochuyen_full_48k-fhg"


# ── Job interface (minimal — match worker contract) ────────────────────────────

# ── Result ─────────────────────────────────────────────────────────────────────

@dataclass
class AnimationResult:
    job_id:          str
    mp4_path:        str
    animation_json:  dict
    duration_ms:     int
    n_scenes:        int
    elapsed_sec:     float
    stages:          dict[str, float] = field(default_factory=dict)  # stage → elapsed


# ── TTS (Vbee) ─────────────────────────────────────────────────────────────────

async def _tts_scene(
    text:        str,
    output_path: str,
    voice_code:  str,
) -> str:
    """
    Gọi Vbee AIVoice TTS cho 1 scene → lưu audio file.

    Returns output_path (dù thành công hay thất bại — caller check os.path.exists).
    """
    from src.core.voice.vbee_engine import VbeeEngine

    try:
        async with VbeeEngine(voice_code=voice_code) as engine:
            result = await engine.generate_voice(
                text=text,
                output_path=output_path,
            )
        if not result.success:
            logger.warning(
                "tts.scene.failed",
                extra={"text_preview": text[:40], "path": output_path},
            )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "tts.scene.error",
            extra={"error": str(exc), "text_preview": text[:40]},
            exc_info=True,
        )

    return output_path


# ── TTS (Vbee) ─────────────────────────────────────────────────────────────────

async def _stage_tts(
    scenes:     list[dict],
    audio_dir:  str,
    voice_code: str = _DEFAULT_VOICE_CODE,
    *,
    job_id:     str = "",          # Fix 3: thêm để log trace
) -> list[str]:
    from src.core.voice.vbee_engine import VbeeEngine

    paths = []
    tasks = []

    for i, scene in enumerate(scenes):
        audio_path = os.path.join(audio_dir, f"scene_{i:02d}.mp3")
        paths.append(audio_path)
        vo = scene.get("voiceover", "").strip()
        if vo:
            tasks.append((vo, audio_path))

    if tasks:
        async with VbeeEngine(voice_code=voice_code) as engine:
            async def _call(text, path):
                try:
                    result = await engine.generate_voice(text=text, output_path=path)
                    if not result.success:
                        logger.warning("tts.scene.failed",
                                       extra={"job_id": job_id,   # Fix 3
                                              "text_preview": text[:40], "path": path})
                except Exception as exc:  # noqa: BLE001
                    logger.error("tts.scene.error",
                                 extra={"job_id": job_id,          # Fix 3
                                        "error": str(exc), "text_preview": text[:40]},
                                 exc_info=True)

            await asyncio.gather(*[_call(vo, path) for vo, path in tasks])

    return paths

# ── ffmpeg mux ─────────────────────────────────────────────────────────────────

def _mux_video_audio(
    video_path:  str,
    audio_paths: list[str],
    output_path: str,
) -> str:
    """
    Ghép video mp4 (no audio) với danh sách audio files → final mp4.

    Nếu không có audio file nào tồn tại, copy video thẳng.
    """

    from imageio_ffmpeg import get_ffmpeg_exe
    ffmpeg = get_ffmpeg_exe()

    existing_audio = [p for p in audio_paths if os.path.exists(p)]

    if not existing_audio:
        shutil.copy2(video_path, output_path)
        logger.info("mux.no_audio — copy video as-is → %s", output_path)
        return output_path

    concat_list  = None
    concat_audio = video_path + "_audio_concat.aac"

    try:
        # Ghi danh sách audio vào file tạm để ffmpeg concat
        with tempfile.NamedTemporaryFile(
            suffix=".txt", delete=False, mode="w", encoding="utf-8"
        ) as f:
            concat_list = f.name
            for ap in existing_audio:
                f.write(f"file '{ap}'\n")

        # Concat + re-encode audio (tránh lỗi khi các stream có sample-rate khác nhau)
        subprocess.run(
            [
                ffmpeg, "-y",
                "-f", "concat", "-safe", "0",
                "-i", concat_list,
                "-c:a", "aac",          # re-encode thay vì -c copy
                "-ar", "48000",         # chuẩn hóa sample-rate
                "-b:a", "128k",
                concat_audio,
            ],
            check=True,
            capture_output=True,
        )

        # Mux video + audio đã concat
        subprocess.run(
            [
                ffmpeg, "-y",
                "-i", video_path,
                "-i", concat_audio,
                "-c:v", "copy",
                "-c:a", "aac",
                "-shortest",
                output_path,
            ],
            check=True,
            capture_output=True,
        )

        logger.info("mux.ok → %s", output_path)

    except subprocess.CalledProcessError as exc:
        logger.error(
            "mux.ffmpeg_failed: %s",
            exc.stderr.decode(errors="replace"),
        )
        shutil.copy2(video_path, output_path)

    finally:
        if concat_list and os.path.exists(concat_list):
            os.unlink(concat_list)
        if os.path.exists(concat_audio):
            os.unlink(concat_audio)

    return output_path


# ── Stage helpers ──────────────────────────────────────────────────────────────

def _build_output_paths(job_id: str, output_dir: str) -> dict[str, str]:
    """Tạo thư mục cần thiết và trả về dict các path dùng trong pipeline."""
    vid_dir = os.path.join(output_dir, "video")
    aud_dir = os.path.join(output_dir, "audio")
    os.makedirs(vid_dir, exist_ok=True)
    os.makedirs(aud_dir, exist_ok=True)
    return {
        "video_raw":   os.path.join(vid_dir, f"{job_id}_raw.mp4"),
        "video_final": os.path.join(vid_dir, f"{job_id}_final.mp4"),
        "audio_dir":   aud_dir,
    }


def _cleanup_raw_video(video_raw: str) -> None:
    """Xóa file video_raw sau khi mux xong để tiết kiệm disk."""
    try:
        if os.path.exists(video_raw):
            os.unlink(video_raw)
            logger.debug("cleanup.video_raw removed: %s", video_raw)
    except OSError as exc:
        logger.warning("cleanup.video_raw failed: %s", exc)


# ── Main pipeline ──────────────────────────────────────────────────────────────
async def run_animation_pipeline(job: Any) -> AnimationResult:
    t0     = time.perf_counter()
    stages: dict[str, float] = {}
    render_cfg         = getattr(job, "render_config", {}) or {}
    topic              = getattr(job, "topic", "") or render_cfg.get("topic", "")
    job_id             = str(job.id if hasattr(job, "id") else job["id"])
    output_dir         = getattr(job, "output_dir", None) or os.path.join(OUTPUT_BASE, job_id)
    n_scenes           = int(render_cfg.get("n_scenes", 3))
    total_duration_ms  = int(render_cfg.get("total_duration_ms", 18_000))
    extra_instructions = render_cfg.get("extra_instructions", "")
    voice_code         = render_cfg.get("voice_code",      "hn_female_ngochuyen_full_48k-fhg")
    tone               = render_cfg.get("tone",            "genz_meme")
    language           = render_cfg.get("language",        "vi")
    story_structure    = render_cfg.get("story_structure", "hook_twist")
    pace               = render_cfg.get("pace",            "balanced")

    if not topic:
        raise ValueError("job.topic hoặc render_config.topic là bắt buộc.")

    paths = _build_output_paths(job_id, output_dir)

    logger.info(
        "[%s] Animation pipeline start — topic=%r, scenes=%d, dur=%dms, voice=%s",
        job_id, topic, n_scenes, total_duration_ms, voice_code,
    )

    # ── Stage 1: Claude → JSON ────────────────────────────────────────────────
    t1 = time.perf_counter()
    async with ClaudeAnimationEngine(retries=MAX_RETRIES) as claude_engine:
        animation_json = await claude_engine.generate(
            topic             = topic,
            tone              = tone,
            language          = language,
            story_structure   = story_structure,
            pace              = pace,
            extra_instructions= extra_instructions,
            merge_defaults    = True,
        )
    stages["claude"] = round(time.perf_counter() - t1, 2)
    logger.info("[%s] Stage 1 (Claude) done in %.1fs", job_id, stages["claude"])

    # Fix 2: Save animation_json vào DB ngay sau Stage 1
    # → nếu crash ở Stage 2/3/4, kịch bản vẫn còn để debug
    try:
        from src.worker.db_helpers import save_metadata_db
        await save_metadata_db(job_id, {
            "animation_json": animation_json,
            "stage1_done": True,
        })
        logger.debug("[%s] Stage 1 JSON saved to DB", job_id)
    except Exception as exc:  # noqa: BLE001 — non-fatal, pipeline tiếp tục
        logger.warning("[%s] Stage 1 DB save failed (non-fatal): %s", job_id, exc)

    scenes = animation_json["scenes"]

    # ── Stage 2 + 3: TTS ∥ Render — chạy song song ───────────────────────────
    t23 = time.perf_counter()

    async def _run_tts() -> list[str]:
        # Fix 3: truyền job_id vào _stage_tts để log có thể trace
        return await _stage_tts(scenes, paths["audio_dir"], voice_code, job_id=job_id)

    async def _run_render() -> None:
        render_engine = StickmanAnimationEngine()
        await asyncio.to_thread(
            render_engine.render_video,
            animation_json,
            paths["video_raw"],
        )

    async with asyncio.TaskGroup() as tg:
        tts_task    = tg.create_task(_run_tts(),    name=f"tts_{job_id}")
        render_task = tg.create_task(_run_render(), name=f"render_{job_id}")

    audio_paths = tts_task.result()
    stages["tts_render_parallel"] = round(time.perf_counter() - t23, 2)
    logger.info(
        "[%s] Stage 2+3 (TTS ∥ Render) done in %.1fs",
        job_id, stages["tts_render_parallel"],
    )

    # ── Stage 4: Mux ──────────────────────────────────────────────────────────
    t4 = time.perf_counter()
    await asyncio.to_thread(
        _mux_video_audio,
        paths["video_raw"],
        audio_paths,
        paths["video_final"],
    )
    stages["mux"] = round(time.perf_counter() - t4, 2)
    logger.info("[%s] Stage 4 (Mux) done in %.1fs", job_id, stages["mux"])

    _cleanup_raw_video(paths["video_raw"])

    elapsed  = round(time.perf_counter() - t0, 2)
    total_ms = sum(s.get("duration_ms", 0) for s in scenes)

    logger.info(
        "[%s] Pipeline DONE in %.1fs — output: %s",
        job_id, elapsed, paths["video_final"],
    )

    return AnimationResult(
        job_id         = job_id,
        mp4_path       = paths["video_final"],
        animation_json = animation_json,
        duration_ms    = total_ms,
        n_scenes       = len(scenes),
        elapsed_sec    = elapsed,
        stages         = stages,
    )