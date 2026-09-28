# src/worker/redis_client.py
from __future__ import annotations
import redis.asyncio as aioredis
from src.config import settings

_redis_client: aioredis.Redis | None = None

def get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
        )
    return _redis_client