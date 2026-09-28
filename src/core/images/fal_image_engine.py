# src/core/images/fal_image_engine.py
"""
FalImageEngine — Image generation via Fal.ai (FLUX.1 Schnell).

Kế thừa BaseImageEngine, implement đúng contract:
  generate_image() → ImageResult  (không phải Optional[str])

generate_images_for_script() được kế thừa từ BaseImageEngine — không override.

Chi phí: ~$0.003/ảnh (576×1024 = 9:16)
Model:   fal-ai/flux/schnell (FLUX.1 [schnell] by Black Forest Labs)

Docs tham khảo:
  https://fal-ai.github.io/fal/client/fal_client.html
  https://fal.ai/models/fal-ai/flux/schnell/api
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any, Final, Literal, Optional

import fal_client
from dotenv import load_dotenv

from .base_image_engine import BaseImageEngine
from ..base_ai_engine import ImageResult
from ...utils.logger import get_logger

load_dotenv()
logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

# FAL_MODEL_ID = "fal-ai/flux/schnell"

FAL_MODEL_ID: Final[dict[str, str]] = {
    "fast":     "fal-ai/flux/schnell",
    "balanced": "xai/grok-imagine-image"
}

# Custom size cho 9:16 chuẩn (576×1024)
DEFAULT_IMAGE_SIZE: dict[str, int] = {"width": 576, "height": 1024}

# Timeout cho fal_client — tổng thời gian chờ queue + inference
# Flux Schnell thường xong trong 3–5s, đặt 60s là đủ rộng
DEFAULT_CLIENT_TIMEOUT: int = 60  # seconds

# HTTP codes nên retry
_RETRYABLE_HTTP_CODES: frozenset[int] = frozenset({
    408, 429, 499, 500, 502, 503, 504,
})

_RETRYABLE_MESSAGES: tuple[str, ...] = (
    "timeout", "rate limit", "server error",
    "service unavailable", "internal error",
)


# ─────────────────────────────────────────────────────────────────────────────
# ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class FalImageEngine(BaseImageEngine):
    """Image-generation engine dùng Fal.ai + FLUX.1 [schnell].

    Thay thế NanoBananaEngine với chi phí thấp hơn ~16x.

    Chi phí thực tế:
        9:16 (576×1024) = ~$0.003/ảnh
        10 ảnh/user/tháng = ~$0.03/user (gói Free)

    Flow theo docs Fal.ai:
        fal_client.subscribe_async() → submit vào queue →
        poll tự động → trả về dict khi COMPLETED → result["images"][0]["url"]

    NOTE: Dùng module-level fal_client.subscribe_async() thay vì AsyncClient
    instance vì subscribe_async() là module-level function, không phải method
    của AsyncClient. AsyncClient chỉ có .subscribe() (không có _async suffix).
    Module-level functions tự đọc FAL_KEY từ env — không cần truyền key thủ công.

    Refs:
        https://fal-ai.github.io/fal/client/fal_client.html
        "Every method in the Python SDK has an async counterpart with an _async
        suffix (e.g., subscribe_async, submit_async, run_async, stream_async)."
        → Đây là module-level, không phải AsyncClient instance method.

    Example::

        async with FalImageEngine() as engine:
            result = await engine.generate_image(
                prompt="stickman with tie pointing at chart, white background",
                output_path="out/scene_001.png",
            )
            if result.success:
                print(result.saved_path)
    """

    def __init__(
        self,
        image_size:            dict[str, int] | str | None = None,
        num_inference_steps:   int                         = 4,
        seed:                  Optional[int]               = None,
        enable_safety_checker: bool                        = True,
        output_format:         Literal["jpeg", "png"]      = "png",
        client_timeout:        int                         = DEFAULT_CLIENT_TIMEOUT,
    ) -> None:
        """Khởi tạo FalImageEngine.

        Args:
            image_size: Dict {"width": int, "height": int} hoặc preset string.
                None → mặc định 9:16 (576×1024).
            num_inference_steps: Số bước inference (1–4). 4 = chất lượng tốt nhất.
            seed: Seed cố định để giữ style nhất quán giữa các ảnh. None = random.
            enable_safety_checker: Bật/tắt safety filter.
            output_format: "png" hoặc "jpeg". png = không mất dữ liệu.
            client_timeout: Tổng thời gian chờ tối đa (giây) cho cả queue + inference.
                Default 60s đủ rộng cho Flux Schnell (thường 3–5s).

        Raises:
            ValueError: Nếu không tìm thấy API key (raise từ BaseEngine).
        """
        # Gọi super() để BaseEngine validate + load self.api_key từ env FAL_KEY
        super().__init__(
            model_name = FAL_MODEL_ID["fast"], 
            env_var    = "FAL_KEY",
        )

        self.image_size            = image_size or DEFAULT_IMAGE_SIZE
        self.num_inference_steps   = num_inference_steps
        self.seed                  = seed
        self.enable_safety_checker = enable_safety_checker
        self.output_format         = output_format
        self.client_timeout        = client_timeout

    # ── Context manager ───────────────────────────────────────────────────────

    async def __aenter__(self) -> FalImageEngine:
        return self

    async def __aexit__(self, *_: Any) -> None:
        pass

    # ── Abstract implementations ──────────────────────────────────────────────

    def _is_retryable(self, error: Exception) -> bool:
        """Xác định lỗi Fal.ai có nên retry hay không."""
        code = getattr(error, "status_code", None) or getattr(error, "code", None)
        if isinstance(code, int) and code in _RETRYABLE_HTTP_CODES:
            return True

        error_str = str(error).lower()
        return any(marker in error_str for marker in _RETRYABLE_MESSAGES)

    async def generate_image(
        self,
        prompt:      str,
        output_path: str | Path,
        image_size:  dict[str, int] | str | None = None,
        use_best_model: bool = False,
        seed:        Optional[int]                = None,
        **_kwargs:   Any,
    ) -> ImageResult:
        """Sinh một ảnh từ prompt và lưu vào output_path.

        Không bao giờ raise — mọi failure path đều trả về
        ``ImageResult(success=False)``.

        Args:
            prompt: Mô tả ảnh bằng English (stickman style).
            output_path: Đường dẫn file đầu ra (.png / .jpeg).
                Thư mục cha được tạo tự động nếu chưa có.
            image_size: Override size cho request này.
                None → dùng engine default (9:16).
            seed: Override seed cho request này. None → dùng engine default.
            **_kwargs: Bỏ qua — forward compatibility với BaseImageEngine.

        Returns:
            ``ImageResult(success=True, saved_path=...)`` nếu thành công.
            ``ImageResult(success=False, error=...)`` nếu lỗi.
        """
        from ...utils.path_utils import to_absolute_path  # local import tránh cycle

        start_ms    = time.monotonic()
        output_path = Path(output_path)
        final_size  = image_size or self.image_size
        final_seed  = seed if seed is not None else self.seed

        output_path.parent.mkdir(parents=True, exist_ok=True)

        if use_best_model:
            self.model_name = FAL_MODEL_ID["balanced"]

        logger.info(
            "[FalImage] model=%s | size=%s | seed=%s | prompt='%.60s'",
            self.model_name, final_size, final_seed, prompt,
        )

        # Gọi Fal.ai queue API
        try:
            fal_result = await self._call_fal(prompt, final_size, final_seed, use_best_model)
        except Exception as exc:  # noqa: BLE001
            logger.error("[FalImage] _call_fal raise: %s", exc)
            return self._failure_result(prompt, start_ms, f"API call thất bại: {exc}")

        if fal_result is None:
            return self._failure_result(
                prompt, start_ms,
                "API returned no response (timeout or quota exceeded)",
            )

        # Download và lưu ảnh
        saved_path = await self._download_and_save(fal_result, output_path)
        if saved_path is None:
            return self._failure_result(
                prompt, start_ms,
                "Không thể download hoặc lưu ảnh từ Fal.ai response.",
            )

        # ★ Convert sang absolute — nhất quán với NanoBanana
        absolute_path = to_absolute_path(saved_path)
        latency_ms    = (time.monotonic() - start_ms) * 1000
        logger.info("[FalImage] ✅ Saved: %s (%.0fms)", absolute_path, latency_ms)

        return ImageResult(
            saved_path = absolute_path,
            model_name = self.model_name,
            prompt     = prompt,
            latency_ms = latency_ms,
            success    = True,
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _call_fal(
        self,
        prompt:     str,
        image_size: dict[str, int] | str,
        seed:       Optional[int],
        use_best_model: bool,
    ) -> Optional[dict]:
        
        # Grok dùng aspect_ratio + resolution thay vì image_size
        if use_best_model:
            arguments: dict[str, Any] = {
                "prompt":        prompt,
                "aspect_ratio":  image_size if isinstance(image_size, str) else "9:16",
                "resolution":    "1k",
                "num_images":    1,
                "output_format": self.output_format,
            }
        else:
            arguments: dict[str, Any] = {
                "prompt":                prompt,
                "image_size":            image_size,
                "num_inference_steps":   self.num_inference_steps,
                "num_images":            1,
                "enable_safety_checker": self.enable_safety_checker,
                "output_format":         self.output_format,
            }

        if seed is not None:
            arguments["seed"] = seed

        model_id = FAL_MODEL_ID["balanced"] if use_best_model else FAL_MODEL_ID["fast"]

        return await fal_client.subscribe_async(
            model_id,
            arguments,
            client_timeout = self.client_timeout,
        )

    async def _download_and_save(
        self,
        fal_result:  dict,
        output_path: Path,
    ) -> Optional[str]:
        """Download ảnh từ URL trong Fal.ai response và lưu ra disk.

        Theo docs, response là dict thuần:
            result["images"][0]["url"] → URL ảnh
            result["images"][0]["width"] / ["height"] → kích thước thực tế

        Args:
            fal_result: dict trả về từ fal_client.subscribe_async().
            output_path: Đường dẫn file đầu ra.

        Returns:
            Đường dẫn (str) nếu thành công, None nếu lỗi.
        """
        # Parse URL ảnh từ response
        try:
            images = fal_result.get("images") or []
            if not images:
                logger.warning("[FalImage] Response không có images.")
                return None

            first_image = images[0]
            image_url   = first_image.get("url") if isinstance(first_image, dict) else None

            if not image_url:
                logger.warning("[FalImage] Image URL rỗng trong response.")
                return None

            logger.debug(
                "[FalImage] Image: %sx%s | type=%s | url=%s",
                first_image.get("width"),
                first_image.get("height"),
                first_image.get("content_type"),
                image_url,
            )

        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            logger.error("[FalImage] Parse images từ response thất bại: %s", exc)
            return None

        # Download ảnh — dùng run_in_executor để không block event loop
        try:
            import httpx

            loop = asyncio.get_running_loop()

            def _download() -> bytes:
                with httpx.Client(timeout=30.0) as client:
                    resp = client.get(image_url)
                    resp.raise_for_status()
                    return resp.content

            image_bytes = await loop.run_in_executor(None, _download)

        except Exception as exc:  # noqa: BLE001
            logger.error(
                "[FalImage] Download ảnh thất bại: %s | url=%s", exc, image_url,
            )
            return None

        # Ghi ra disk
        try:
            output_path.write_bytes(image_bytes)
            return str(output_path)
        except OSError as exc:
            logger.error(
                "[FalImage] Ghi file thất bại: %s | path=%s", exc, output_path,
            )
            return None

    def _failure_result(
        self,
        prompt:    str,
        start_ms:  float,
        error_msg: str,
    ) -> ImageResult:
        """Tạo ImageResult thất bại với latency chính xác."""
        return ImageResult(
            saved_path = None,
            model_name = self.model_name,
            prompt     = prompt,
            latency_ms = (time.monotonic() - start_ms) * 1000,
            success    = False,
            error      = error_msg,
        )