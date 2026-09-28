# src/core/security/global_cap.py
"""
Lớp 5 — Cầu dao điện: Global Daily Cap
Đếm tổng số video toàn hệ thống trong ngày.
Nếu vượt ngưỡng chi phí → chặn toàn bộ request tạo video.

Backend ưu tiên: Redis (atomic INCR, tự expire)
Fallback: File JSON (dùng khi dev local không có Redis)
"""
import json
import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, status
from src.utils.logger import get_logger

logger = get_logger(__name__)

# ── Cấu hình ─────────────────────────────────────────────────────────────────
# Điều chỉnh 2 biến này theo chi phí thực tế của bạn
COST_PER_VIDEO_VND  = int(os.getenv("COST_PER_VIDEO_VND",  "5000"))
MAX_DAILY_COST_VND  = int(os.getenv("MAX_DAILY_COST_VND",  "600000"))
DAILY_VIDEO_LIMIT   = MAX_DAILY_COST_VND // COST_PER_VIDEO_VND   # 120 video/ngày

# ── Redis setup ───────────────────────────────────────────────────────────────
try:
    import redis.asyncio as aioredis
    _redis: aioredis.Redis = aioredis.from_url(
        os.getenv("REDIS_URL", "redis://localhost:6379"),
        encoding="utf-8",
        decode_responses=True,
    )
    USE_REDIS = True
except ImportError:
    USE_REDIS = False
    logger.warning("redis-py không được cài — GlobalCap dùng file fallback.")


def _today_key() -> str:
    """Key theo ngày UTC: global_video_cap:2025-07-15"""
    return f"global_video_cap:{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"


# ── Redis backend ─────────────────────────────────────────────────────────────
async def _redis_get() -> int:
    val = await _redis.get(_today_key())
    return int(val) if val else 0


async def _redis_increment() -> int:
    key   = _today_key()
    count = await _redis.incr(key)
    await _redis.expire(key, 90_000)   # 25h — an toàn qua nửa đêm UTC
    return count


# ── File fallback ─────────────────────────────────────────────────────────────
_CAP_FILE  = Path("/tmp/global_video_cap.json")
_file_lock = asyncio.Lock()


def _file_read() -> dict:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if _CAP_FILE.exists():
        try:
            data = json.loads(_CAP_FILE.read_text())
            if data.get("date") == today:
                return data
        except (json.JSONDecodeError, KeyError):
            pass
    return {"date": today, "count": 0}


def _file_write(data: dict) -> None:
    _CAP_FILE.write_text(json.dumps(data))


async def _file_get() -> int:
    async with _file_lock:
        return _file_read()["count"]


async def _file_increment() -> int:
    async with _file_lock:
        data = _file_read()
        data["count"] += 1
        _file_write(data)
        return data["count"]


# ── Public API ────────────────────────────────────────────────────────────────
async def get_daily_count() -> int:
    if USE_REDIS:
        return await _redis_get()
    return await _file_get()


async def check_and_increment_global_cap() -> int:
    """
    Gọi hàm này TRƯỚC khi trừ credit và tạo job.
    Raise HTTP 503 nếu đã chạm ngưỡng chi phí ngày.
    Trả về số lượt đã dùng sau khi tăng.
    """
    current = await get_daily_count()

    if current >= DAILY_VIDEO_LIMIT:
        logger.warning(
            "GlobalCap chạm ngưỡng: %d/%d video hôm nay (~%s VNĐ)",
            current, DAILY_VIDEO_LIMIT,
            f"{current * COST_PER_VIDEO_VND:,}",
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": "Hệ thống đang bảo trì tạm thời, vui lòng thử lại sau.",
                "retry_after_seconds": 3600,
            },
        )

    new_count = await (_redis_increment() if USE_REDIS else _file_increment())
    logger.info("GlobalCap: %d/%d video hôm nay", new_count, DAILY_VIDEO_LIMIT)
    return new_count


async def get_cap_status() -> dict:
    """Dùng cho endpoint admin /admin/cap-status."""
    count = await get_daily_count()
    return {
        "date":              datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "used":              count,
        "limit":             DAILY_VIDEO_LIMIT,
        "remaining":         max(0, DAILY_VIDEO_LIMIT - count),
        "estimated_cost_vnd": count * COST_PER_VIDEO_VND,
        "max_cost_vnd":      MAX_DAILY_COST_VND,
        "is_capped":         count >= DAILY_VIDEO_LIMIT,
        "backend":           "redis" if USE_REDIS else "file",
    }