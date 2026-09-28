# === src/worker/redis_semaphore.py ===
"""Global render semaphore qua Redis — giới hạn MoviePy trên TOÀN VPS.

Vấn đề hiện tại:
    asyncio.Semaphore là in-process → 4 worker container = 4 semaphore riêng
    → 4 MoviePy render song song → tranh RAM → OOM/swap → chậm

Giải pháp:
    Dùng Redis SET để track active render slots.
    Tất cả worker container share cùng 1 counter.

Thiết kế:
    - SETNX để acquire slot (atomic)
    - TTL để tự release nếu worker crash (không deadlock)
    - Exponential backoff để chờ slot
"""
from __future__ import annotations

import asyncio
import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

from redis.asyncio import Redis
from src.utils.logger import get_logger

logger = get_logger(__name__)
import os
from typing import Final

# ─── Config ──────────────────────────────────────────────────────────────────
GLOBAL_RENDER_SLOTS: int       = 2
FAL_SLOTS:           Final[int] = int(os.getenv("FAL_CONCURRENCY",  "2"))
VBEE_SLOTS:          Final[int] = int(os.getenv("VBEE_CONCURRENCY", "2"))

SLOT_TTL_SECONDS:        int   = 300
ACQUIRE_TIMEOUT_SECONDS: float = 900.0
_POLL_MIN: float = 2.0
_POLL_MAX: float = 15.0


# ─── Core chung ──────────────────────────────────────────────────────────────
@asynccontextmanager
async def _acquire_slot(
    redis:      Redis,
    prefix:     str,
    max_slots:  int,
    job_id:     str,
) -> AsyncIterator[str]:
    slot_id  = f"{job_id}:{uuid.uuid4().hex[:8]}"
    key      = f"{prefix}:{slot_id}"
    acquired = False
    deadline = time.monotonic() + ACQUIRE_TIMEOUT_SECONDS
    wait_s   = _POLL_MIN

    logger.info(f"{prefix}.waiting", extra={"job_id": job_id, "max_slots": max_slots})

    try:
        while time.monotonic() < deadline:
            active = len(await redis.keys(f"{prefix}:*"))

            if active < max_slots:
                ok = await redis.set(key, str(job_id), nx=True, ex=SLOT_TTL_SECONDS)
                if ok:
                    acquired = True
                    logger.info(f"{prefix}.acquired", extra={
                        "job_id": job_id, "slot_id": slot_id,
                        "active_now": active + 1, "max_slots": max_slots,
                    })
                    break

            logger.info(f"{prefix}.waiting_poll", extra={
                "job_id": job_id, "active": active,
                "max_slots": max_slots, "wait_s": round(wait_s, 1),
            })
            await asyncio.sleep(wait_s)
            wait_s = min(wait_s * 1.5, _POLL_MAX)

        if not acquired:
            active = len(await redis.keys(f"{prefix}:*"))
            raise TimeoutError(
                f"[{job_id}] Không acquire {prefix} sau "
                f"{ACQUIRE_TIMEOUT_SECONDS:.0f}s — active={active}/{max_slots}"
            )

        yield slot_id

    finally:
        if acquired:
            await redis.delete(key)
            logger.info(f"{prefix}.released", extra={"job_id": job_id, "slot_id": slot_id})


# ─── Public API ──────────────────────────────────────────────────────────────
@asynccontextmanager
async def acquire_render_slot(redis: Redis, job_id: str) -> AsyncIterator[str]:
    async with _acquire_slot(redis, "render_slot", GLOBAL_RENDER_SLOTS, job_id) as slot:
        yield slot


@asynccontextmanager
async def acquire_fal_slot(redis: Redis, job_id: str) -> AsyncIterator[str]:
    async with _acquire_slot(redis, "fal_slot", FAL_SLOTS, job_id) as slot:
        yield slot


@asynccontextmanager
async def acquire_vbee_slot(redis: Redis, job_id: str) -> AsyncIterator[str]:
    async with _acquire_slot(redis, "vbee_slot", VBEE_SLOTS, job_id) as slot:
        yield slot