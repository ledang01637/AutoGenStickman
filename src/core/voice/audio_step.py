# === src/core/worker/audio_step.py ===
"""Stage 3 — TTS với VbeeEngine + concurrency gate + per-scene retry."""
from __future__ import annotations

import asyncio
import os
import random
from pathlib import Path
from typing import Any, Final
from redis.asyncio import Redis

from ..voice.vbee_engine import (
    VbeeAudioExpiredError,
    VbeeAuthError,
    VbeeBusinessError,
    VbeeEngine,
    VbeeRateLimitError,
    VbeeTransientError,
)
from ...worker.db_helpers import load_metadata_db, update_scene_field
from ...worker.redis_client import get_redis
from ...worker.redis_semaphore import acquire_vbee_slot
from ...utils.logger import get_logger
from ...utils.path_utils import to_absolute_path
from ...utils.scene_naming import scene_filename_index

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────
# ★ ĐÃ XÓA: PACE_TO_SPEED_RATE và pace_to_speed_rate()
# Lý do: speed_rate là thuộc tính của PaceProfile (src/domain/pace.py).
# Single source of truth — audio_step chỉ ĐỌC speed_rate từ meta_data.

_MAX_RETRIES_PER_SCENE: Final[int]   = 1
_RETRY_BASE_DELAY:      Final[float] = 2.0
_RETRY_MAX_DELAY:       Final[float] = 30.0

_DEFAULT_VOICE_CODE: Final[str] = "hn_female_ngochuyen_full_48k-fhg"
_DEFAULT_SPEED_RATE: Final[float] = 1.0  # Fallback nếu meta thiếu speed_rate
_SUCCESS_RATE_INFO_THRESHOLD: Final[float] = 0.9


# ─────────────────────────────────────────────────────────────────────────────
# Stats helper
# ─────────────────────────────────────────────────────────────────────────────

class _SceneStats:
    """Aggregate stats cho 1 batch."""

    def __init__(self, total: int) -> None:
        self.total   = total
        self.success = 0
        self.failed  = 0
        self.skipped = 0

    def record_success(self) -> None: self.success += 1
    def record_failed(self)  -> None: self.failed  += 1
    def record_skipped(self) -> None: self.skipped += 1

    @property
    def success_rate(self) -> float:
        attempted = self.total - self.skipped
        return (self.success / attempted) if attempted > 0 else 1.0


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

async def generate_audio_step(
    job_id:     str,
    audios_dir: Path,
    voice_code: str | None = None,
) -> None:
    """Stage 3 — Generate voiceover cho mọi scene của job.

    speed_rate được ĐỌC từ meta_data (đã set bởi Stage 1 dựa trên pace).
    audio_step KHÔNG quyết định speed_rate — đó là việc của pace.py.

    Args:
        job_id:     Job ID.
        audios_dir: Output directory cho .mp3.
        voice_code: Vbee voice code. None → env hoặc default.
    """
    data = await load_metadata_db(job_id)

    if not data or "scenes" not in data:
        logger.warning("audio_step.no_data", extra={"job_id": job_id})
        return

    audios_dir.mkdir(parents=True, exist_ok=True)
    scenes = data["scenes"]
    meta   = data.get("meta_data", {})
    stats  = _SceneStats(total=len(scenes))
    redis = get_redis()

    # Resolve voice_code: param > env > default
    resolved_voice_code = (
        voice_code
        or os.getenv("VBEE_VOICE_CODE", "").strip()
        or _DEFAULT_VOICE_CODE
    )

    # ★ KEY FIX: Đọc speed_rate từ meta (đã được pace.py tính)
    # KHÔNG map lại từ pace_key — single source of truth là pace.py
    speed_rate = float(meta.get("speed_rate", _DEFAULT_SPEED_RATE))
    pace_key   = meta.get("pace", "balanced")

    logger.info(
        "audio_step.start",
        extra={
            "job_id":         job_id,
            "num_scenes":     len(scenes),
            "voice_code":     resolved_voice_code,
            "pace":           pace_key,
            "speed_rate":     speed_rate,
            "max_retries":    _MAX_RETRIES_PER_SCENE,
        },
    )

    async with VbeeEngine(
        voice_code=resolved_voice_code,
        speed_rate=speed_rate,
    ) as engine:
        if not await engine.health_check():
            logger.error(
                "audio_step.health_check_failed",
                extra={"job_id": job_id, "action": "abort_batch"},
            )
            await _mark_all_scenes_failed(job_id, scenes)
            return

        async with asyncio.TaskGroup() as tg:
            for i, scene in enumerate(scenes):
                tg.create_task(
                    _process_one_scene(
                        engine=engine, 
                        redis=redis, 
                        stats=stats,
                        job_id=job_id, 
                        scene_idx=i, 
                        scene=scene,
                        audios_dir=audios_dir,
                    ),
                    name=f"audio_scene_{i}",
                )

    log_method = (
        logger.info
        if stats.success_rate >= _SUCCESS_RATE_INFO_THRESHOLD
        else logger.error
    )
    log_method(
        "audio_step.done",
        extra={
            "job_id":       job_id,
            "total":        stats.total,
            "success":      stats.success,
            "failed":       stats.failed,
            "skipped":      stats.skipped,
            "success_rate": round(stats.success_rate, 3),
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# Per-scene processing (KHÔNG đổi)
# ─────────────────────────────────────────────────────────────────────────────

async def _process_one_scene(
    engine:     VbeeEngine,
    redis:      Redis,
    stats:      _SceneStats,
    job_id:     str,
    scene_idx:  int,
    scene:      dict[str, Any],
    audios_dir: Path,
) -> None:
    """Process 1 scene với retry loop."""
    scene_id = scene.get("scene_id", str(scene_idx + 1))

    if scene.get("status", {}).get("audio") == "completed":
        stats.record_skipped()
        return

    voiceover = scene.get("voiceover", "").strip()
    if not voiceover:
        logger.warning(
            "audio_step.scene.empty_voiceover",
            extra={"job_id": job_id, "scene_id": scene_id},
        )
        stats.record_skipped()
        return

    index = scene_filename_index(scene_id)
    save_path = audios_dir / f"scene_{index}.mp3"

    success, attempts_used = await _generate_with_retry(
        engine=engine, 
        redis=redis, 
        text=voiceover, 
        save_path=save_path,
        job_id=job_id, 
        scene_id=scene_id,
    )

    status_value = "completed" if success else "failed"
    path_value = to_absolute_path(save_path) if success else ""
    await update_scene_field(
        job_id=job_id, scene_idx=scene_idx, kind="audio",
        status_value=status_value, path_value=path_value,
    )

    if success:
        stats.record_success()
        logger.info(
            "audio_step.scene.ok",
            extra={"job_id": job_id, "scene_id": scene_id, "attempts": attempts_used},
        )
    else:
        stats.record_failed()
        logger.error(
            "audio_step.scene.failed_final",
            extra={"job_id": job_id, "scene_id": scene_id, "attempts": attempts_used},
        )


# ─────────────────────────────────────────────────────────────────────────────
# Retry logic (KHÔNG đổi)
# ─────────────────────────────────────────────────────────────────────────────

async def _generate_with_retry(
    engine:    VbeeEngine,
    redis:     Redis,
    text:      str,
    save_path: Path,
    job_id:    str,
    scene_id:  str,
) -> tuple[bool, int]:
    """Generate với exponential backoff retry."""
    last_error_type: str = "unknown"

    for attempt in range(1, _MAX_RETRIES_PER_SCENE + 1):
        try:
            async with acquire_vbee_slot(redis, job_id):  
                result = await engine.generate_voice(
                    text=text, output_path=save_path,
                )
            if result.success:
                return True, attempt

            last_error_type = (
                f"engine_returned_failure: "
                f"{result.error[:100] if result.error else 'unknown'}"
            )
            logger.warning(
                "audio_step.scene.engine_returned_failure",
                extra={
                    "job_id": job_id, "scene_id": scene_id,
                    "attempt": attempt, "error": result.error,
                },
            )

        except VbeeAuthError as exc:
            logger.error(
                "audio_step.scene.auth_error",
                extra={"job_id": job_id, "scene_id": scene_id, "error": str(exc)},
            )
            return False, attempt

        except VbeeBusinessError as exc:
            logger.error(
                "audio_step.scene.business_error",
                extra={
                    "job_id": job_id, "scene_id": scene_id,
                    "attempt": attempt, "error": str(exc),
                },
            )
            return False, attempt

        except VbeeRateLimitError as exc:
            last_error_type = "rate_limit"
            logger.warning(
                "audio_step.scene.rate_limited",
                extra={
                    "job_id": job_id, "scene_id": scene_id,
                    "attempt": attempt, "retry_after_s": exc.retry_after,
                },
            )

        except (VbeeTransientError, VbeeAudioExpiredError) as exc:
            last_error_type = type(exc).__name__
            logger.warning(
                "audio_step.scene.transient_error",
                extra={
                    "job_id": job_id, "scene_id": scene_id,
                    "attempt": attempt, "error": str(exc),
                },
            )

        except Exception as exc:  # noqa: BLE001
            last_error_type = type(exc).__name__
            logger.error(
                "audio_step.scene.unexpected_error",
                extra={
                    "job_id": job_id, "scene_id": scene_id,
                    "attempt": attempt, "error_type": type(exc).__name__,
                    "error": str(exc),
                },
                exc_info=True,
            )

        if attempt < _MAX_RETRIES_PER_SCENE:
            backoff_max = min(
                _RETRY_BASE_DELAY * (2 ** (attempt - 1)),
                _RETRY_MAX_DELAY,
            )
            backoff = random.uniform(_RETRY_BASE_DELAY, backoff_max * 1.5)
            logger.info(
                "audio_step.scene.retry_backoff",
                extra={
                    "job_id": job_id, "scene_id": scene_id,
                    "attempt": attempt, "next_attempt_in_s": round(backoff, 2),
                    "last_error": last_error_type,
                },
            )
            await asyncio.sleep(backoff)

    return False, _MAX_RETRIES_PER_SCENE


# ─────────────────────────────────────────────────────────────────────────────
# Helpers (KHÔNG đổi)
# ─────────────────────────────────────────────────────────────────────────────

async def _mark_all_scenes_failed(
    job_id: str, scenes: list[dict[str, Any]],
) -> None:
    """Mark tất cả scenes failed (dùng khi health check fail)."""
    for i in range(len(scenes)):
        await update_scene_field(
            job_id=job_id, scene_idx=i, kind="audio",
            status_value="failed", path_value="",
        )
    logger.error(
        "audio_step.all_marked_failed",
        extra={"job_id": job_id, "count": len(scenes)},
    )