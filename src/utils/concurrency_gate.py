# === src/utils/concurrency_gate.py ===
"""Concurrency gates cho providers có hard concurrent limit.

KHÁC với rate limiter (RPS): concurrency gate giới hạn số requests
ĐANG chạy đồng thời, không quan tâm tốc độ.

Use case:
    - Typecast: max 2 concurrent (theo docs.typecast.ai)
    - Vbee: ~3 concurrent conservative (docs không nói rõ)
    - Một số API có hard concurrent limit khác

Pattern:
    1. Acquire semaphore slot (blocking nếu đầy)
    2. Check global 429 backoff window
    3. Yield → caller fire request
    4. Release slot khi exit context

Race-safe: notify_429() từ task A sẽ block tasks B, C, D đang chờ slot
qua double-check pattern.
"""
from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator, Final

from .logger import get_logger

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

_DEFAULT_BACKOFF_SECONDS: Final[float] = 5.0
_MAX_BACKOFF_CAP_SECONDS: Final[float] = 60.0


# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ConcurrencyConfig:
    """Cấu hình concurrency gate cho 1 provider.

    Attributes:
        max_concurrent: Số requests tối đa đang chạy đồng thời.
        provider_name:  Tên provider để log/debug.
    """

    max_concurrent: int
    provider_name:  str

    def __post_init__(self) -> None:
        if self.max_concurrent < 1:
            raise ValueError(
                f"{self.provider_name}: max_concurrent phải >= 1, "
                f"got {self.max_concurrent}"
            )
        if not self.provider_name.strip():
            raise ValueError("provider_name không được rỗng")


# Per-provider configs — match docs từng provider
TYPECAST_CONCURRENCY: Final[ConcurrencyConfig] = ConcurrencyConfig(
    max_concurrent=2,         # docs.typecast.ai: max 2 concurrent
    provider_name="typecast",
)

VBEE_CONCURRENCY: Final[ConcurrencyConfig] = ConcurrencyConfig(
    max_concurrent=3,         # Vbee docs không document rõ — conservative
    provider_name="vbee",
)


# ─────────────────────────────────────────────────────────────────────────────
# GATE
# ─────────────────────────────────────────────────────────────────────────────

class ConcurrencyGate:
    """Gate giới hạn số concurrent requests + global 429 backoff.

    Pattern: Semaphore (concurrency cap) + Lock (backoff coordination)
    + double-check (race-safe khi notify trong lúc tasks chờ slot).

    Thread-safety: 1 instance dùng cho nhiều coroutines của cùng 1 provider.
    KHÔNG share giữa providers khác nhau (mỗi provider có gate riêng).

    Example::

        gate = ConcurrencyGate(VBEE_CONCURRENCY)

        async with gate.acquire():
            try:
                response = await vbee_api()
            except RateLimitError as exc:
                await gate.notify_429(exc.retry_after)
                raise
    """

    def __init__(self, config: ConcurrencyConfig) -> None:
        """Khởi tạo gate.

        Args:
            config: ConcurrencyConfig của provider.
        """
        self._config = config
        self._semaphore = asyncio.Semaphore(config.max_concurrent)
        self._backoff_until_monotonic: float = 0.0
        self._backoff_lock = asyncio.Lock()

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[None]:
        """Acquire 1 slot. Block đến khi:
            1. Backoff window expired (nếu có 429 gần đây)
            2. Có slot trống (< max_concurrent đang chạy)

        Pattern: double-check backoff để race-safe khi tasks khác
        notify_429 trong lúc ta đang chờ semaphore.

        Yields:
            None khi safe để fire request.

        Example::

            async with gate.acquire():
                response = await api_call()
        """
        # Bước 1: Wait global backoff TRƯỚC khi acquire slot
        # (nếu đã biết đang trong backoff thì không tốn slot)
        await self._wait_for_backoff()

        # Bước 2: Acquire concurrency slot
        async with self._semaphore:
            # Bước 3: Re-check backoff sau khi pass semaphore
            # Race scenario: task khác notify_429 trong lúc ta chờ slot.
            # Double-check để đảm bảo respect backoff mới nhất.
            await self._wait_for_backoff()

            # Bước 4: Yield → caller fire request
            yield

    async def notify_429(
        self, retry_after_seconds: float | None = None,
    ) -> None:
        """Caller gọi khi nhận 429 → tất cả task khác sẽ wait.

        Args:
            retry_after_seconds: Từ Retry-After header. None → dùng default.
                Cap tại _MAX_BACKOFF_CAP_SECONDS để không stuck quá lâu.
        """
        delay = (
            retry_after_seconds
            if retry_after_seconds is not None
            else _DEFAULT_BACKOFF_SECONDS
        )
        capped = min(max(delay, 0.0), _MAX_BACKOFF_CAP_SECONDS)

        async with self._backoff_lock:
            now = time.monotonic()
            new_until = now + capped
            # Chỉ update nếu xa hơn (nhiều task notify cùng lúc → race-safe)
            if new_until > self._backoff_until_monotonic:
                self._backoff_until_monotonic = new_until
                logger.warning(
                    "concurrency_gate.backoff_set",
                    extra={
                        "provider":               self._config.provider_name,
                        "retry_after_s":          capped,
                        "backoff_until_monotonic": new_until,
                    },
                )

    async def _wait_for_backoff(self) -> None:
        """Sleep cho đến khi backoff window expire."""
        now = time.monotonic()
        wait = self._backoff_until_monotonic - now
        if wait > 0:
            logger.info(
                "concurrency_gate.waiting_backoff",
                extra={
                    "provider": self._config.provider_name,
                    "seconds":  round(wait, 2),
                },
            )
            await asyncio.sleep(wait)

    @property
    def provider_name(self) -> str:
        """Tên provider — readonly, dùng cho log."""
        return self._config.provider_name

    @property
    def max_concurrent(self) -> int:
        """Số concurrent tối đa — readonly."""
        return self._config.max_concurrent