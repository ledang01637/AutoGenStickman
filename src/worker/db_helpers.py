# === src/worker/db_helpers.py ===
"""Database helpers — atomic finalize + JSONB partial updates."""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.types import String

from src.core.database.db import AsyncSessionLocal
from src.core.database.schemas import RenderJobStatus
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def load_metadata_db(job_id: str) -> dict[str, Any] | None:
    query = text("SELECT render_config FROM render_jobs WHERE id = :id")
    async with AsyncSessionLocal() as session:
        result = await session.execute(query, {"id": job_id})
        row = result.fetchone()
        return row.render_config if row else None


async def save_metadata_db(job_id: str, data: dict[str, Any]) -> None:
    query = text("""
        UPDATE render_jobs
        SET render_config = CAST(:config AS JSONB), updated_at = NOW()
        WHERE id = :id
    """)
    async with AsyncSessionLocal() as session:
        await session.execute(query, {
            "config": json.dumps(data, ensure_ascii=False),
            "id": job_id,
        })
        await session.commit()


async def update_scene_field(
    job_id:       str,
    scene_idx:    int,
    kind:         str,
    status_value: str,
    path_value:   str | None = None,
) -> None:
    """Partial update scene status + path qua jsonb_set (race-safe)."""
    if kind not in ("image", "audio", "video"):
        raise ValueError(f"kind phải là 'image'/'audio'/'video', got {kind!r}")
    if not isinstance(scene_idx, int) or scene_idx < 0:
        raise ValueError(f"scene_idx phải >= 0, got {scene_idx!r}")

    if path_value is None:
        # Chỉ update status
        query = text("""
            UPDATE render_jobs
            SET render_config = jsonb_set(
                    render_config, :status_path, to_jsonb(:status_value)
                ),
                updated_at = NOW()
            WHERE id = :id
        """).bindparams(
            bindparam("status_path", type_=ARRAY(String)),
            bindparam("status_value", type_=String),
        )
        async with AsyncSessionLocal() as session:
            await session.execute(query, {
                "id": job_id,
                "status_path": ["scenes", str(scene_idx), "status", kind],
                "status_value": status_value,
            })
            await session.commit()
        return

    # Update cả status và path
    query = text("""
        UPDATE render_jobs
        SET render_config = jsonb_set(
                jsonb_set(render_config, :status_path, to_jsonb(:status_value)),
                :path_path, to_jsonb(:path_value)
            ),
            updated_at = NOW()
        WHERE id = :id
    """).bindparams(
        bindparam("status_path",  type_=ARRAY(String)),
        bindparam("path_path",    type_=ARRAY(String)),
        bindparam("status_value", type_=String),
        bindparam("path_value",   type_=String),
    )
    async with AsyncSessionLocal() as session:
        await session.execute(query, {
            "id": job_id,
            "status_path": ["scenes", str(scene_idx), "status", kind],
            "path_path":   ["scenes", str(scene_idx), "paths",  kind],
            "status_value": status_value,
            "path_value":   path_value,
        })
        await session.commit()


async def fetch_and_lock_job(worker_id: str) -> dict | None:
    """
    FIX Bug 2: Gộp reset + lock vào 1 CTE atomic — tránh race condition
    nhiều workers cùng reset 1 job.

    Eligible jobs:
    - PENDING (fresh start)
    - FAILED với retry_count < max_retries
    - PROCESSING timeout (>15 phút) với retry_count < max_retries
    """
    async with AsyncSessionLocal() as session:
        # Tách join ra để debug rõ hơn khi xảy ra
        result = await session.execute(text("""
            WITH eligible AS (
                SELECT rj.id, rj.project_id
                FROM render_jobs rj
                WHERE (
                    (rj.status = 'PENDING')
                    OR (rj.status = 'FAILED'      AND rj.retry_count < rj.max_retries)
                    OR (rj.status = 'PROCESSING'
                        AND rj.locked_at < NOW() - INTERVAL '15 minutes'
                        AND rj.retry_count < rj.max_retries)
                )
                AND rj.deleted_at IS NULL
                ORDER BY
                    CASE rj.status WHEN 'PENDING' THEN 0 ELSE 1 END,
                    rj.priority DESC,
                    rj.created_at ASC
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            )
            UPDATE render_jobs rj
            SET status      = 'PROCESSING',
                locked_at   = NOW(),
                worker_id   = :worker_id,
                started_at  = COALESCE(rj.started_at, NOW()),
                retry_count = CASE
                    WHEN rj.status IN ('FAILED', 'PROCESSING') THEN rj.retry_count + 1
                    ELSE rj.retry_count
                END
            FROM eligible
            LEFT JOIN video_projects vp ON vp.id = eligible.project_id  
            WHERE rj.id = eligible.id
            RETURNING
                rj.id, rj.render_config, rj.cost_credits,
                rj.project_id, rj.retry_count, rj.max_retries,
                rj.duration_seconds, rj.scenes_count,
                vp.user_id
        """), {"worker_id": worker_id})

        await session.commit()
        row = result.mappings().fetchone()
        
        return dict(row) if row else None

async def fetch_job_by_id(job_id: str) -> dict | None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                SELECT rj.id, rj.render_config, rj.cost_credits,
                       rj.project_id, rj.retry_count, rj.max_retries,
                       rj.duration_seconds, rj.scenes_count,
                       vp.user_id
                FROM render_jobs rj
                LEFT JOIN video_projects vp ON vp.id = rj.project_id
                WHERE rj.id = :id
                  AND rj.deleted_at IS NULL
            """),
            {"id": job_id},
        )
        row = result.mappings().fetchone()
        return dict(row) if row else None


async def update_job_status(job_id: str, status: RenderJobStatus) -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(
            text("""
                UPDATE render_jobs
                SET status     = :status,
                    updated_at = NOW()
                WHERE id = :id
            """),
            {"status": status.value, "id": job_id},
        )
        await session.commit()

async def finalize_job_atomic(
    job_id:         str,
    status:         RenderJobStatus,
    output_url:     str = "",
    error_msg:      str = "",
    refund_user_id: str | None = None,
    refund_amount:  int | None = None,
) -> None:
    """
    FIX Bug 3: Đọc retry_count TRƯỚC khi UPDATE để tránh điều kiện refund
    luôn sai do đã increment retry_count rồi mới check.
    """
    async with AsyncSessionLocal() as session:
        async with session.begin():
            if status == RenderJobStatus.FAILED:
                row = await session.execute(
                    text("SELECT retry_count, max_retries FROM render_jobs WHERE id = :id"),
                    {"id": job_id},
                )
                job_row = row.fetchone()
                new_retry    = (job_row.retry_count + 1) if job_row else 1
                is_exhausted = job_row and (new_retry >= job_row.max_retries)

                await session.execute(text("""
                    UPDATE render_jobs
                    SET retry_count   = retry_count + 1,
                        status        = 'FAILED',
                        error_message = NULLIF(:err, ''),
                        completed_at  = CASE
                                          WHEN retry_count + 1 >= max_retries THEN NOW()
                                          ELSE NULL
                                        END,
                        locked_at     = NULL,
                        worker_id     = NULL
                    WHERE id = :id
                """), {"err": error_msg, "id": job_id})

                # Chỉ refund khi:
                # 1. Hết retry (is_exhausted)
                # 2. Job thực sự đã bị trừ credit — kiểm tra qua credit_transactions
                if is_exhausted and refund_user_id and refund_amount:
                    consumed = await session.scalar(
                        text("""
                            SELECT COUNT(*) FROM credit_transactions
                            WHERE render_job_id = :jid
                              AND user_id = :uid
                              AND transaction_type = 'CONSUME'
                        """),
                        {"jid": job_id, "uid": refund_user_id},
                    )
                    if consumed and consumed > 0:
                        await session.execute(
                            text("SELECT refund_credits(:uid, :amount, :jid)"),
                            {"uid": refund_user_id, "amount": refund_amount, "jid": job_id},
                        )
                        logger.info("job.refund", extra={
                            "job_id": job_id, "user_id": refund_user_id,
                            "amount": refund_amount, "retry_exhausted": True,
                        })
                    else:
                        logger.warning("job.refund_skipped_no_consume", extra={
                            "job_id": job_id,
                        })
                else:
                    logger.info("job.will_retry", extra={
                        "job_id": job_id, "retry": new_retry,
                        "max": job_row.max_retries if job_row else "?",
                    })

            else:
                # COMPLETED hoặc INSUFFICIENT_CREDITS
                await session.execute(text("""
                    UPDATE render_jobs
                    SET status        = :status,
                        output_url    = NULLIF(:url, ''),
                        error_message = NULL,
                        completed_at  = NOW(),
                        locked_at     = NULL,
                        worker_id     = NULL
                    WHERE id = :id
                """), {"status": status.value, "url": output_url, "id": job_id})

                if (status == RenderJobStatus.INSUFFICIENT_CREDITS
                        and refund_user_id and refund_amount):
                    await session.execute(
                        text("SELECT refund_credits(:uid, :amount, :jid)"),
                        {"uid": refund_user_id, "amount": refund_amount, "jid": job_id},
                    )

            logger.info("job.finalized", extra={
                "job_id": job_id,
                "status": status.value,
            })