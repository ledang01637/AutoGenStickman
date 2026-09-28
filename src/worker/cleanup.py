# === src/core/worker/cleanup.py ===
"""Background cleanup — xóa job folders > 1 giờ, có Redis lock chống race condition."""
from __future__ import annotations

import asyncio
import shutil
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import redis.asyncio as aioredis
from sqlalchemy import text

from src.core.database.db import AsyncSessionLocal
from src.utils.logger import get_logger

logger = get_logger(__name__)

JOBS_BASE_DIR      = Path("/app/jobs")
CLEANUP_INTERVAL_S = 30 * 60
JOB_TTL_HOURS      = 1

# Redis lock config
LOCK_KEY           = "cleanup:primary_lock"
LOCK_TTL_S         = 25 * 60  


async def _try_acquire_lock(redis: aioredis.Redis) -> bool:
    """SET NX EX — chỉ 1 worker acquire được lock tại một thời điểm."""
    return await redis.set(LOCK_KEY, "1", nx=True, ex=LOCK_TTL_S)


async def _get_completed_job_folders(cutoff: datetime) -> list:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                SELECT id, output_url
                FROM render_jobs
                WHERE completed_at < :cutoff
                  AND status IN ('COMPLETED', 'FAILED')
                  AND deleted_at IS NULL
            """),
            {"cutoff": cutoff},
        )
        return result.fetchall()


async def _mark_deleted(job_ids: list[int]) -> None:
    """Cập nhật deleted_at để tránh query lại ở lần cleanup sau."""
    if not job_ids:
        return
    async with AsyncSessionLocal() as session:
        await session.execute(
            text("""
                UPDATE render_jobs
                SET deleted_at = :now
                WHERE id = ANY(:ids)
            """),
            {"now": datetime.now(timezone.utc), "ids": job_ids},
        )
        await session.commit()


async def cleanup_old_jobs() -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=JOB_TTL_HOURS)

    try:
        rows = await _get_completed_job_folders(cutoff)
    except Exception as exc:
        logger.error("cleanup.db_error", extra={"error": str(exc)}, exc_info=True)
        return

    deleted    = 0
    errors     = 0
    deleted_ids: list[int] = []

    for row in rows:
        if not row.output_url:
            continue

        try:
            parts = row.output_url.split("/app/jobs/")
            if len(parts) < 2:
                continue

            job_folder_name = parts[1].split("/")[0]
            job_path = JOBS_BASE_DIR / job_folder_name

            if not job_path.exists():
                # Folder đã mất — vẫn mark deleted để không query lại
                deleted_ids.append(row.id)
                continue

            shutil.rmtree(job_path)
            deleted_ids.append(row.id)
            deleted += 1
            logger.info("cleanup.deleted", extra={"folder": str(job_path)})

        except Exception as exc:
            errors += 1
            logger.error(
                "cleanup.delete_failed",
                extra={"url": row.output_url, "error": str(exc)},
            )

    # Commit deleted_at một lần sau khi xử lý toàn bộ batch
    try:
        await _mark_deleted(deleted_ids)
    except Exception as exc:
        logger.error("cleanup.mark_deleted_failed", extra={"error": str(exc)}, exc_info=True)

    logger.info(
        "cleanup.done",
        extra={"deleted": deleted, "errors": errors, "cutoff": cutoff.isoformat()},
    )


async def cleanup_loop() -> None:
    """
    Background loop — chỉ worker acquire được Redis lock mới thực thi cleanup.
    Các worker còn lại sleep rồi thử lại ở interval tiếp theo.
    """
    logger.info("cleanup.loop.start")

    REDIS_URL =  os.getenv("REDIS_URL", "redis://redis:6379/0")

    redis = aioredis.from_url(REDIS_URL, decode_responses=True)

    try:
        while True:
            await asyncio.sleep(CLEANUP_INTERVAL_S)

            try:
                acquired = await _try_acquire_lock(redis)
            except Exception as exc:
                logger.error("cleanup.lock_error", extra={"error": str(exc)}, exc_info=True)
                continue

            if not acquired:
                logger.info("cleanup.lock_skipped")  # worker khác đang chạy
                continue

            await cleanup_old_jobs()
    finally:
        await redis.aclose()