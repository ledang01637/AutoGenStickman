
# === src/core/images/nano_banana_engine.py ===
"""
NanoBananaEngine — Image generation via Google Gemini (Nano Banana models).

Kế thừa BaseImageEngine, implement đúng contract:
  generate_image() → ImageResult  (không phải Optional[str])

generate_images_for_script() được kế thừa từ BaseImageEngine — không override.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any, Literal, Optional

from google import genai
from google.genai import types
from google.genai import errors as genai_errors
from dotenv import load_dotenv

from .base_image_engine import BaseImageEngine
from ..base_ai_engine import ImageResult
from ...utils.logger import get_logger

load_dotenv()
logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

NANO_BANANA_MODELS: dict[str, str] = {
    "fast":    "gemini-3.1-flash-image-preview",
    "quality": "gemini-3-pro-image-preview",
}

AspectRatio = Literal[
    "1:1", "1:4", "1:8", "2:3", "3:2", "3:4",
    "4:1", "4:3", "4:5", "5:4", "8:1", "9:16", "16:9", "21:9",
]

Resolution = Literal["512", "1K", "2K", "4K"]

_RETRYABLE_HTTP_CODES: frozenset[int] = frozenset({
    408, 429, 499, 500, 502, 503, 504,
})


# ─────────────────────────────────────────────────────────────────────────────
# ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class NanoBananaEngine(BaseImageEngine):
    """Image-generation engine dùng Google Nano Banana (Gemini image models).

    Models:
        fast    → gemini-3.1-flash-image-preview  (nhanh, rẻ, high-volume)
        quality → gemini-3-pro-image-preview       (chất lượng cao)

    Example::

        async with NanoBananaEngine(model="fast") as engine:
            result = await engine.generate_image(
                prompt="stickman with tie",
                output_path="out/scene_001.png",
            )
            if result.success:
                print(result.saved_path)
    """

    def __init__(
        self,
        api_key:      Optional[str] = None,
        model:        Literal["fast", "quality"] = "fast",
        aspect_ratio: AspectRatio = "9:16",
        resolution:   Resolution  = "512",
    ) -> None:
        """Khởi tạo NanoBananaEngine.

        Args:
            api_key: Gemini API key. None → đọc từ env ``GEMINI_API_KEY``.
            model: Tier model. ``"fast"`` cho throughput cao,
                ``"quality"`` cho độ chính xác cao hơn.
            aspect_ratio: Tỉ lệ khung hình mặc định.
            resolution: Độ phân giải mặc định.

        Raises:
            ValueError: Nếu không tìm thấy API key.
        """

        super().__init__(
            model_name = NANO_BANANA_MODELS[model],
            env_var    = "GEMINI_API_KEY",
        )

        self._genai_client = genai.Client(api_key=self.api_key)
        self.tier          = model
        self.aspect_ratio  = aspect_ratio
        self.resolution    = resolution

    # ── Context manager ───────────────────────────────────────────────────────

    async def __aenter__(self) -> NanoBananaEngine:
        return self

    async def __aexit__(self, *_: Any) -> None:
        pass

    # ── Abstract implementations ──────────────────────────────────────────────

    def _is_retryable(self, error: Exception) -> bool:
        """Xác định lỗi Gemini API có nên retry hay không."""
        if isinstance(error, genai_errors.ServerError):
            return True

        if isinstance(error, genai_errors.APIError):
            code = getattr(error, "code", None)
            return isinstance(code, int) and code in _RETRYABLE_HTTP_CODES

        try:
            import httpx
            if isinstance(error, (
                httpx.TimeoutException, httpx.ConnectError,
                httpx.RemoteProtocolError, httpx.ReadError,
            )):
                return True
        except ImportError:
            pass

        transient_markers = (
            "ResourceExhausted", "ServiceUnavailable",
            "DeadlineExceeded",  "InternalServerError", "Aborted",
        )
        return any(m in type(error).__name__ for m in transient_markers)

    async def generate_image(
        self,
        prompt:       str,
        output_path:  str | Path,
        aspect_ratio: AspectRatio | None = None,
        resolution:   Resolution | None  = None,
        **_kwargs:    Any,
    ) -> ImageResult:
        """Sinh ảnh và lưu — saved_path luôn absolute."""
        from ...utils.path_utils import to_absolute_path  # local import tránh cycle

        start_ms    = time.monotonic()
        output_path = Path(output_path)
        final_ratio = aspect_ratio or self.aspect_ratio
        final_res   = resolution   or self.resolution

        output_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(
            "[NanoBanana] model=%s | ratio=%s | res=%s | prompt='%.60s'",
            self.model_name, final_ratio, final_res, prompt,
        )

        try:
            response = await self._call_genai(prompt, final_ratio, final_res)
        except Exception as exc:  # noqa: BLE001
            logger.error("[NanoBanana] _call_genai raise: %s", exc)
            return self._failure_result(prompt, start_ms, f"API call thất bại: {exc}")

        if response is None:
            return self._failure_result(
                prompt, start_ms,
                "API returned no response (timeout or quota exceeded)",
            )

        saved_path = self._extract_and_save_image(response, output_path)
        if saved_path is None:
            return self._failure_result(
                prompt, start_ms, "Model không trả về ảnh trong response.",
            )

        # ★ FIX: Convert sang absolute để Stage 4 không phụ thuộc cwd
        absolute_path = to_absolute_path(saved_path)
        latency_ms = (time.monotonic() - start_ms) * 1000
        logger.info("[NanoBanana] ✅ Saved: %s (%.0fms)", absolute_path, latency_ms)

        return ImageResult(
            saved_path = absolute_path,
            model_name = self.model_name,
            prompt     = prompt,
            latency_ms = latency_ms,
            success    = True,
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _call_genai(
        self,
        prompt:       str,
        aspect_ratio: AspectRatio,
        resolution:   Resolution,
    ) -> Any:
        """Gọi Gemini API trong thread executor (client là sync).

        Args:
            prompt: Mô tả ảnh.
            aspect_ratio: Tỉ lệ khung hình.
            resolution: Độ phân giải.

        Returns:
            Response object từ genai, hoặc None nếu lỗi.

        Raises:
            google.genai.errors.APIError: Lỗi từ API.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self._genai_client.models.generate_content(
                model    = self.model_name,
                contents = prompt,
                config   = types.GenerateContentConfig(
                    response_modalities = ["IMAGE", "TEXT"],
                    image_config        = types.ImageConfig(
                        aspect_ratio = aspect_ratio,
                        image_size   = resolution,
                    ),
                ),
            ),
        )

    def _extract_and_save_image(
        self,
        response:    Any,
        output_path: Path,
    ) -> Optional[str]:
        """Trích xuất ảnh đầu tiên từ response và lưu ra disk.

        Caller đảm bảo response không phải None trước khi gọi method này.

        Args:
            response: Response object từ genai API (không phải None).
            output_path: Đường dẫn file đầu ra.

        Returns:
            Đường dẫn tuyệt đối (str) nếu lưu thành công, None nếu không có ảnh.
        """
        if not response.candidates:
            logger.warning("[NanoBanana] Response không có candidates.")
            return None

        for part in response.candidates[0].content.parts:
            image = part.as_image()
            if image is not None:
                image.save(str(output_path))
                return str(output_path)

        logger.warning("[NanoBanana] Không tìm thấy ảnh trong response.")
        return None

    def _failure_result(
        self,
        prompt:    str,
        start_ms:  float,
        error_msg: str,
    ) -> ImageResult:
        """Tạo ImageResult thất bại với latency chính xác.

        Args:
            prompt: Prompt gốc.
            start_ms: Thời điểm bắt đầu (monotonic) để tính latency.
            error_msg: Mô tả nguyên nhân thất bại.

        Returns:
            ImageResult với success=False.
        """
        return ImageResult(
            saved_path = None,
            model_name = self.model_name,
            prompt     = prompt,
            latency_ms = (time.monotonic() - start_ms) * 1000,
            success    = False,
            error      = error_msg,
        )

