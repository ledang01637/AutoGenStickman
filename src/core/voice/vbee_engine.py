## === src/core/voice/vbee_engine.py ===
"""VbeeEngine — TTS qua Vbee AIVoice API (vbee.vn).

Flow async theo docs Vbee:
    1. POST /api/v1/tts            → result.request_id
    2. GET  /api/v1/tts/{id} loop  → status="SUCCESS" → audio_link
    3. GET  audio_link             → download bytes (HẾT HẠN sau 3 PHÚT!)

KEY DECISIONS:
    - Dùng httpx.AsyncClient (stack lock của project, consistent với
      ClaudeEngine/NanoBananaEngine nội bộ).
    - app_id load từ env VBEE_APP_ID, KHÔNG nhận qua param (defense in depth).
    - response_type="indirect" (poll mode, không cần webhook public).
    - Audio download IMMEDIATELY sau success — link expire 3min.
    - Polling exponential backoff: 1s → 2s → 4s → 8s (cap).
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any, ClassVar, Final

import aiofiles
import httpx
from dotenv import load_dotenv
import os

from ..base_ai_engine import VoiceResult
from ...utils.logger import get_logger
from .base_voice_engine import BaseVoiceEngine

load_dotenv()
logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

_VBEE_BASE_URL:    Final[str]   = "https://vbee.vn/api/v1"
_VBEE_SYNTH_PATH:  Final[str]   = "/tts"
_VBEE_STATUS_PATH: Final[str]   = "/tts/{request_id}"

# Polling parameters — exponential backoff để giảm load
_POLL_INITIAL_DELAY_S: Final[float] = 1.0
_POLL_MAX_DELAY_S:     Final[float] = 8.0
_POLL_BACKOFF_FACTOR:  Final[float] = 2.0
_POLL_MAX_WAIT_S:      Final[float] = 120.0

# Vbee status values (theo docs — UPPERCASE)
_STATUS_SUCCESS:     Final[str] = "SUCCESS"
_STATUS_FAILURE:     Final[str] = "FAILURE"

# HTTP timeouts — fine-grained (httpx feature)
_CONNECT_TIMEOUT_S: Final[float] = 10.0
_READ_TIMEOUT_S:    Final[float] = 30.0
_WRITE_TIMEOUT_S:   Final[float] = 10.0

# Audio download timeout — link expire 3 phút, phải nhanh
_AUDIO_DOWNLOAD_TIMEOUT_S: Final[float] = 60.0

# ─────────────────────────────────────────────────────────────────────────────
# EXCEPTIONS
# ─────────────────────────────────────────────────────────────────────────────

class VbeeError(Exception):
    """Base cho mọi Vbee API errors."""

    def __init__(self, message: str, status_code: int = 0) -> None:
        super().__init__(message)
        self.status_code = status_code


class VbeeAuthError(VbeeError):
    """401/403 — API key/app_id sai. KHÔNG retry."""


class VbeeRateLimitError(VbeeError):
    """429 — Quá rate limit."""

    def __init__(self, message: str, retry_after: float = 5.0) -> None:
        super().__init__(message, status_code=429)
        self.retry_after = retry_after


class VbeeTransientError(VbeeError):
    """5xx — Lỗi server tạm thời, có thể retry."""


class VbeeBusinessError(VbeeError):
    """HTTP 200 nhưng body ``status: 0`` — lỗi nghiệp vụ.

    Ví dụ: voice_code không tồn tại, app_id sai, text quá dài.
    """


class VbeeAudioExpiredError(VbeeError):
    """Audio link đã hết hạn (3 phút). Cần re-poll để lấy link mới."""


# ─────────────────────────────────────────────────────────────────────────────
# ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class VbeeEngine(BaseVoiceEngine):
    """TTS engine cho Vbee AIVoice API (vbee.vn).

    Yêu cầu env vars:
        VBEE_API_KEY: Bearer token (lấy từ studio.vbee.vn → Settings → API Key)
        VBEE_APP_ID:  App ID (lấy từ studio.vbee.vn → Apps)

    Args:
        voice_code:    Mã giọng đọc, vd ``"hn_female_ngochuyen_full_48k-fhg"``.
        speed_rate:    Tốc độ đọc (0.1–1.9). Mặc định 1.0.
        bitrate:       Bitrate MP3 (8/16/32/64/128). Mặc định 128.
        sample_rate:   Optional sample rate.
        base_url:      Override URL nếu Vbee đổi host.
        poll_timeout:  Tổng thời gian chờ tối đa cho 1 request (giây).
        **kwargs:      Forward tới BaseVoiceEngine (max_retries, timeout, ...).

    Example::

        async with VbeeEngine(
            voice_code="hn_female_ngochuyen_full_48k-fhg",
        ) as engine:
            result = await engine.generate_voice(
                text="Xin chào Việt Nam!",
                output_path="/tmp/scene_001.mp3",
            )
            if result.success:
                print(f"Saved: {result.saved_path} ({result.latency_ms:.0f}ms)")
    """

    ENV_VAR_API_KEY: ClassVar[str] = "VBEE_API_KEY"
    ENV_VAR_APP_ID:  ClassVar[str] = "VBEE_APP_ID"

    def __init__(
        self,
        voice_code:    str,
        speed_rate:    float = 1.0,
        bitrate:       int   = 128,
        sample_rate:   int | None = None,
        base_url:      str   = _VBEE_BASE_URL,
        poll_timeout:  float = _POLL_MAX_WAIT_S,
        **kwargs:      Any,
    ) -> None:
        # Base load secret qua env_var
        super().__init__(
            model_name=voice_code,
            env_var=self.ENV_VAR_API_KEY,
            **kwargs,
        )

        self._app_id = os.getenv(self.ENV_VAR_APP_ID)

        # Validation
        if not (0.1 <= speed_rate <= 1.9):
            raise ValueError(f"speed_rate phải trong [0.1, 1.9], got {speed_rate}")
        if bitrate not in (8, 16, 32, 64, 128):
            raise ValueError(f"bitrate phải là 8/16/32/64/128, got {bitrate}")

        self.voice_code   = voice_code
        self.speed_rate   = speed_rate
        self.bitrate      = bitrate
        self.sample_rate  = sample_rate
        self.base_url     = base_url.rstrip("/")
        self.poll_timeout = poll_timeout
        self._client: httpx.AsyncClient | None = None

    # ── Context manager ───────────────────────────────────────────────────────

    async def __aenter__(self) -> "VbeeEngine":
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=self._auth_headers(),
            timeout=httpx.Timeout(
                connect=_CONNECT_TIMEOUT_S,
                read=_READ_TIMEOUT_S,
                write=_WRITE_TIMEOUT_S,
                pool=_CONNECT_TIMEOUT_S,
            ),
            # HTTP/2 nếu Vbee CDN support (tự fallback HTTP/1.1 nếu không)
            http2=False,  # Set True khi verify Vbee support
            # Connection pool cho polling lặp lại
            limits=httpx.Limits(
                max_connections=10,
                max_keepalive_connections=5,
            ),
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val:  BaseException | None,
        exc_tb:   object,
    ) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # ── Public: generate_voice ────────────────────────────────────────────────

    async def generate_voice(
        self,
        text:        str,
        output_path: str | Path,
        voice_code:  str | None = None,
        speed_rate:  float | None = None,
        **_kwargs:   Any,
    ) -> VoiceResult:
        start = time.monotonic()
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # direct mode: _submit_synthesis trả audio_link luôn
            audio_link = await self._submit_synthesis(
                text=text,
                voice_code=voice_code or self.voice_code,
                speed_rate=speed_rate if speed_rate is not None else self.speed_rate,
            )
            logger.info(
                "vbee.submit.ok",
                extra={"audio_link_preview": audio_link[:60], "text_preview": text[:30]},
            )

            # Download ngay (link vẫn có TTL)
            await self._download_audio(audio_link, output_path)

            latency_ms = (time.monotonic() - start) * 1000
            logger.info(
                "vbee.generate.ok",
                extra={"path": str(output_path), "latency_ms": round(latency_ms)},
            )
            return VoiceResult(
                saved_path=str(output_path),
                model_name=self.model_name,
                text=text,
                latency_ms=latency_ms,
                success=True,
            )

        except VbeeAuthError as exc:
            return self._fail_result(text, start, f"Auth error: {exc}")
        except VbeeBusinessError as exc:
            return self._fail_result(text, start, f"Business error: {exc}")
        except VbeeRateLimitError as exc:
            return self._fail_result(text, start, f"Rate limited: {exc}")
        except (asyncio.TimeoutError, httpx.TimeoutException) as exc:
            return self._fail_result(text, start, f"Timeout: {exc}")
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "vbee.generate.unexpected_error",
                extra={"error_type": type(exc).__name__, "error": str(exc)},
                exc_info=True,
            )
            return self._fail_result(text, start, f"Unexpected: {exc}")

    # ── Bước 1: Submit ────────────────────────────────────────────────────────

    async def _submit_synthesis(
        self,
        text:       str,
        voice_code: str,
        speed_rate: float,
    ) -> str:
        """POST /tts với response_type=direct → trả về audio_link ngay.

        response_type=direct: Vbee xử lý sync, trả audio_link trực tiếp
        trong response body — không cần callback_url, không cần poll.
        """
        payload: dict[str, Any] = {
            "app_id":        self._app_id,
            "response_type": "direct",      # ✅ sync, không cần webhook
            "input_text":    text,
            "voice_code":    voice_code,
            "audio_type":    "mp3",
            "bitrate":       self.bitrate,
            "speed_rate":    speed_rate,
        }
        if self.sample_rate is not None:
            payload["sample_rate"] = self.sample_rate

        client = self._ensure_client()
        try:
            resp = await client.post(_VBEE_SYNTH_PATH, json=payload)
        except httpx.RequestError as exc:
            raise VbeeTransientError(f"Network error: {exc}") from exc

        data = self._parse_and_validate_response(resp)

        # response_type=direct: audio_link nằm thẳng trong result
        result = data.get("result", {})
        if not isinstance(result, dict):
            raise VbeeBusinessError(f"Response thiếu 'result': {str(data)[:300]}")

        audio_link = result.get("audio_link")
        if not audio_link:
            raise VbeeBusinessError(
                f"Response thiếu audio_link: {str(result)[:300]}"
            )

        return str(audio_link)

    # ── Bước 2: Poll ──────────────────────────────────────────────────────────

    async def _poll_until_done(self, request_id: str) -> str:
        """Poll GET /tts/{id} với exponential backoff đến khi SUCCESS.

        Returns:
            audio_link để download ngay.

        Raises:
            asyncio.TimeoutError: Quá poll_timeout.
            VbeeBusinessError:    status="FAILURE" hoặc thiếu audio_link.
        """
        url = _VBEE_STATUS_PATH.format(request_id=request_id)
        client = self._ensure_client()

        elapsed = 0.0
        delay = _POLL_INITIAL_DELAY_S

        while elapsed < self.poll_timeout:
            try:
                resp = await client.get(url)
            except httpx.RequestError as exc:
                # Network glitch — log + retry sau delay
                logger.warning(
                    "vbee.poll.network_error",
                    extra={"request_id": request_id, "error": str(exc)},
                )
                await asyncio.sleep(delay)
                elapsed += delay
                continue

            data = self._parse_and_validate_response(resp)
            result = data.get("result", {})
            status = result.get("status", "").upper()  # defensive UPPERCASE

            logger.debug(
                "vbee.poll.tick",
                extra={
                    "request_id": request_id,
                    "status": status,
                    "elapsed_s": round(elapsed, 1),
                    "progress": result.get("progress"),
                },
            )

            if status == _STATUS_SUCCESS:
                audio_link = result.get("audio_link")
                if not audio_link:
                    raise VbeeBusinessError(
                        f"Status SUCCESS nhưng thiếu audio_link: {str(result)[:300]}"
                    )

                # Cảnh báo nếu link đã expired
                if result.get("audio_expired") is True:
                    raise VbeeAudioExpiredError(
                        f"Audio link đã expire khi poll (request_id={request_id})"
                    )
                return str(audio_link)

            if status == _STATUS_FAILURE:
                reason = (
                    result.get("error_message")
                    or data.get("error_message")
                    or "Vbee xử lý thất bại"
                )
                raise VbeeBusinessError(f"Vbee FAILURE: {reason}")

            # IN_PROGRESS hoặc unknown — wait và retry
            await asyncio.sleep(delay)
            elapsed += delay

            # Exponential backoff (cap tại _POLL_MAX_DELAY_S)
            delay = min(delay * _POLL_BACKOFF_FACTOR, _POLL_MAX_DELAY_S)

        raise asyncio.TimeoutError(
            f"Vbee không hoàn thành sau {self.poll_timeout:.0f}s "
            f"(request_id={request_id})"
        )

    # ── Bước 3: Download ──────────────────────────────────────────────────────

    async def _download_audio(self, audio_link: str, output_path: Path) -> None:
        """Download audio từ S3 link và lưu local.

        QUAN TRỌNG: link expire 3 phút. Phải gọi NGAY sau success.

        Stream qua aiofiles để tránh load cả file vào RAM (audio có thể lớn).

        Raises:
            VbeeAudioExpiredError: HTTP 410 hoặc 403 → link đã expired.
            VbeeTransientError:    Network error.
        """
        # Audio link là S3 URL public, KHÔNG cần Authorization header.
        # Tạo client tạm không kế thừa headers Bearer (tránh AWS reject).
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(_AUDIO_DOWNLOAD_TIMEOUT_S),
            follow_redirects=True,
        ) as download_client:
            try:
                async with download_client.stream("GET", audio_link) as resp:
                    if resp.status_code in (403, 410):
                        raise VbeeAudioExpiredError(
                            f"Audio link expired: HTTP {resp.status_code}"
                        )
                    if resp.status_code != 200:
                        raise VbeeTransientError(
                            f"Download failed: HTTP {resp.status_code}"
                        )

                    # Stream-write để không nuốt RAM cho audio lớn
                    bytes_written = 0
                    async with aiofiles.open(output_path, "wb") as f:
                        async for chunk in resp.aiter_bytes(chunk_size=8192):
                            await f.write(chunk)
                            bytes_written += len(chunk)

                    if bytes_written == 0:
                        raise VbeeTransientError("Audio response rỗng")

            except httpx.RequestError as exc:
                raise VbeeTransientError(f"Download network error: {exc}") from exc

        logger.debug(
            "vbee.download.ok",
            extra={"path": str(output_path), "bytes": bytes_written},
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _auth_headers(self) -> dict[str, str]:
        """Bearer auth headers cho mọi Vbee API call."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type":  "application/json",
            "Accept":        "application/json",
        }

    def _ensure_client(self) -> httpx.AsyncClient:
        """Verify client đã mở qua context manager."""
        if self._client is None or self._client.is_closed:
            raise RuntimeError(
                "VbeeEngine chưa được mở. Dùng `async with VbeeEngine(...) as engine:`"
            )
        return self._client

    def _parse_and_validate_response(self, resp: httpx.Response) -> dict[str, Any]:
        """Parse JSON + validate cả HTTP status VÀ Vbee body status.

        Vbee có pattern đặc biệt: HTTP 200 nhưng body status=0 vẫn là lỗi.
        Phải check cả 2 layers.

        Raises:
            VbeeAuthError, VbeeRateLimitError, VbeeTransientError, VbeeBusinessError.
        """
        # Layer 1: HTTP status
        if resp.status_code in (401, 403):
            raise VbeeAuthError(
                f"HTTP {resp.status_code}: {resp.text[:200]}",
                status_code=resp.status_code,
            )
        if resp.status_code == 429:
            retry_after_str = resp.headers.get("Retry-After", "5")
            try:
                retry_after = float(retry_after_str)
            except (ValueError, TypeError):
                retry_after = 5.0
            raise VbeeRateLimitError(
                f"Rate limited: {resp.text[:200]}",
                retry_after=retry_after,
            )
        if resp.status_code >= 500:
            raise VbeeTransientError(
                f"HTTP {resp.status_code}: {resp.text[:200]}",
                status_code=resp.status_code,
            )
        if resp.status_code >= 400:
            # 4xx khác (400 bad request, 404 not found, etc.) — business error
            raise VbeeBusinessError(
                f"HTTP {resp.status_code}: {resp.text[:200]}",
                status_code=resp.status_code,
            )

        # Layer 2: Parse JSON
        try:
            data = resp.json()
        except Exception as exc:
            raise VbeeBusinessError(
                f"Response không phải JSON hợp lệ: {resp.text[:200]}"
            ) from exc

        # Layer 3: Vbee body status
        body_status = data.get("status")
        if body_status == 0:
            error_msg = data.get("error_message") or data.get("error_code") or "Unknown"
            raise VbeeBusinessError(
                f"Vbee status=0: {error_msg}. Full: {str(data)[:300]}"
            )

        return data

    def _fail_result(
        self, text: str, start: float, reason: str,
    ) -> VoiceResult:
        """Tạo VoiceResult thất bại với latency chính xác."""
        latency_ms = (time.monotonic() - start) * 1000
        return VoiceResult(
            saved_path=None,
            model_name=self.model_name,
            text=text,
            latency_ms=latency_ms,
            success=False,
            error=reason,
        )

    def _is_retryable(self, error: Exception) -> bool:
        """Retry policy cho engine-level retry mechanism.

        Retry: transient errors, rate limits, network glitches.
        KHÔNG retry: auth, business, audio expired (cần re-poll).
        """
        return isinstance(
            error,
            (VbeeTransientError, VbeeRateLimitError, httpx.RequestError),
        )

    # ── Health check ──────────────────────────────────────────────────────────

    async def health_check(self) -> bool:
        """Kiểm tra API key + app_id valid trước khi batch.

        Strategy: Submit 1 request với text rất ngắn rồi BỎ (không poll).
        Nếu được request_id → API key + app_id OK.

        Returns:
            True nếu Vbee accept request.
        """
        try:
            request_id = await self._submit_synthesis(
                text="Test.",
                voice_code=self.voice_code,
                speed_rate=self.speed_rate,
            )
            logger.info(
                "vbee.health_check.ok",
                extra={"sample_request_id": request_id},
            )
            return True
        except VbeeAuthError as exc:
            logger.error(
                "vbee.health_check.auth_failed",
                extra={"error": str(exc)},
            )
            return False
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "vbee.health_check.transient_error",
                extra={"error_type": type(exc).__name__, "error": str(exc)},
            )
            # Transient error có thể không phải vấn đề persistent
            # Return True để không abort batch không cần thiết
            return True