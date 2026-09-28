# src/core/images/base_image_engine.py
"""
TẦNG 2B — BaseImageEngine

Lớp trừu tượng dùng chung cho tất cả image-generation engines
(NanaBananaEngine, ImagenEngine, DallEEngine, ...).

Không chứa: token limit, content filter, budget.
Cung cấp: contract generate_image(), orchestration generate_images_for_script().
"""

from __future__ import annotations

import asyncio
from abc import abstractmethod
from pathlib import Path
from typing import Any, Awaitable, Callable, List, Optional

from ..base_ai_engine import BaseEngine, ImageResult
from ...utils.logger import get_logger
from ...utils.scene_naming import scene_filename_index

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

_IMAGE_STATUS_COMPLETED = "completed"
_IMAGE_STATUS_FAILED    = "failed"
_SCENE_FILENAME_PATTERN = "scene_{index}.png"


# ─────────────────────────────────────────────────────────────────────────────
# TYPE ALIASES
# ─────────────────────────────────────────────────────────────────────────────

# Callback gọi sau khi mỗi scene xong (thành công hay thất bại).
#
# Args:
#     scene_idx: Index 0-based của scene trong list scenes.
#     result:    ImageResult đầy đủ (success, saved_path, error, latency_ms, ...).
#
# Mục đích chính: cho phép caller partial-update DB sau mỗi scene
# thay vì chờ batch xong, tránh race condition khi chạy song song với
# audio step hoặc các task khác cùng ghi vào render_config.
#
# Exception từ callback sẽ propagate lên caller — caller tự catch nếu cần.
SceneDoneCallback = Callable[[int, ImageResult], Awaitable[None]]


# ─────────────────────────────────────────────────────────────────────────────
# BASE CLASS
# ─────────────────────────────────────────────────────────────────────────────

class BaseImageEngine(BaseEngine):
    """Lớp trừu tượng cho image-generation engines.

    Mở rộng ``BaseEngine`` với:
    - Contract ``generate_image()`` trả về ``ImageResult`` nhất quán.
    - Orchestration ``generate_images_for_script()`` tái sử dụng cho mọi engine con.

    Subclasses phải implement:
        _is_retryable(error): Xác định lỗi nào được retry.
        generate_image(prompt, output_path, **kwargs): Sinh một ảnh.

    Example::

        class MyEngine(BaseImageEngine):
            def _is_retryable(self, error):
                return isinstance(error, TransientError)

            async def generate_image(self, prompt, output_path, **kwargs):
                ...
    """

    def __init__(
        self,
        model_name: str,
        env_var: str,
        **kwargs: Any,
    ) -> None:
        """Khởi tạo BaseImageEngine.

        Args:
            model_name: Tên model (bắt buộc, không được rỗng).
            env_var: Tên biến môi trường chứa API key (bắt buộc).
            **kwargs: Truyền tiếp xuống BaseEngine
                (max_retries, timeout, retry_base_delay, ...).
        """
        super().__init__(model_name=model_name, env_var=env_var, **kwargs)

    # ── Abstract contract ─────────────────────────────────────────────────────

    @abstractmethod
    async def generate_image(
        self,
        prompt: str,
        output_path: str | Path,
        use_best_model: bool = False,
        **kwargs: Any,
    ) -> ImageResult:
        """Sinh một ảnh từ prompt và lưu vào output_path.

        Contract quan trọng:
        - **Không** raise Exception khi model từ chối/không tạo được ảnh.
        - Trả về ``ImageResult(success=False, error=<lý do>)`` thay thế.
        - Chỉ raise khi gặp lỗi hạ tầng không thể phục hồi
          (ví dụ: disk full, permission denied).

        Args:
            prompt: Mô tả ảnh. English cho kết quả tốt nhất.
            output_path: Đường dẫn file đầu ra (kể cả tên file và đuôi .png).
                Thư mục cha sẽ được tự động tạo nếu chưa tồn tại.
            **kwargs: Thông số tuỳ engine (aspect_ratio, resolution, ...).

        Returns:
            ImageResult với ``success=True`` và ``saved_path`` nếu thành công,
            hoặc ``success=False`` và ``error`` mô tả nguyên nhân thất bại.
        """

    # ── Orchestration ─────────────────────────────────────────────────────────

    async def generate_images_for_script(
        self,
        scenes: List[dict],
        images_dir: str | Path,
        delay_seconds: float = 3.0,
        use_best_model: bool = False,
        on_scene_done: Optional[SceneDoneCallback] = None,
        **kwargs: Any,
    ) -> List[dict]:
        """Sinh ảnh cho toàn bộ danh sách scene trong một kịch bản.

        Cập nhật ``scene["status"]["image"]`` và ``scene["paths"]["image"]``
        trực tiếp trên từng dict (in-place mutation — caller nhận lại list đã
        được cập nhật).

        Xử lý an toàn:
        - Scene đã ``"completed"`` → bỏ qua (idempotent, hỗ trợ resume).
        - Scene thiếu ``image_prompt`` → đánh dấu ``"failed"``, tiếp tục.
        - Delay giữa các scene để tránh rate-limit (trừ scene cuối).

        Args:
            scenes: List các scene dict từ ``ClaudeEngine.generate_video_script()``.
                Mỗi scene cần có ``scene_id`` và ``image_prompt``.
            images_dir: Thư mục lưu file ảnh. Được tạo tự động nếu chưa có.
            delay_seconds: Giây nghỉ giữa mỗi lần gọi API.
                Đặt ``0.0`` cho testing hoặc khi provider không rate-limit.
            on_scene_done: Async callback gọi sau mỗi scene (thành công hoặc
                thất bại). Signature: ``async def cb(scene_idx, result)``.
                Dùng để partial-update DB trong pipeline song song,
                tránh race condition với task khác cùng ghi render_config.
            **kwargs: Forwarded tới ``generate_image()``
                (aspect_ratio, resolution, ...).

        Returns:
            Danh sách ``scenes`` gốc đã được cập nhật paths + status in-place.
        """
        images_dir = Path(images_dir)
        images_dir.mkdir(parents=True, exist_ok=True)

        total = len(scenes)
        for index, scene in enumerate(scenes):
            await self._process_single_scene(
                scene         = scene,
                index         = index,
                total         = total,
                images_dir    = images_dir,
                delay_seconds = delay_seconds,
                use_best_model = use_best_model,
                on_scene_done = on_scene_done,
                **kwargs,
            )

        return scenes

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _process_single_scene(
        self,
        scene: dict,
        index: int,
        total: int,
        images_dir: Path,
        delay_seconds: float,
        use_best_model: bool,
        on_scene_done: Optional[SceneDoneCallback] = None,
        **kwargs: Any,
    ) -> None:
        """Xử lý một scene: validate → generate → update status → callback → delay.

        Args:
            scene: Dict của scene cần xử lý (mutated in-place).
            index: Vị trí 0-based trong danh sách (dùng cho log và delay).
            total: Tổng số scene (dùng cho log).
            images_dir: Thư mục đích lưu ảnh.
            delay_seconds: Số giây chờ sau khi xử lý (bỏ qua ở scene cuối).
            on_scene_done: Async callback ``(scene_idx, result)`` gọi sau mỗi scene.
            **kwargs: Forwarded tới ``generate_image()``.
        """
        scene_id = scene.get("scene_id", str(index + 1))

        if self._is_scene_already_done(scene, scene_id):
            return

        prompt = self._extract_prompt(scene, scene_id)
        if prompt is None:
            # _extract_prompt đã set status = "failed" trong scene dict.
            # Vẫn gọi callback để DB được cập nhật ngay, không chờ cuối batch.
            if on_scene_done:
                await on_scene_done(index, ImageResult(
                    saved_path = None,
                    model_name = self.model_name,
                    prompt     = "",
                    latency_ms = 0.0,
                    success    = False,
                    error      = "Thiếu image_prompt",
                ))
            return

        output_path = self._build_output_path(images_dir, scene_id)
        logger.info(
            "[%s] [%d/%d] Sinh ảnh cảnh '%s' → %s",
            self.model_name, index + 1, total, scene_id, output_path.name,
        )

        result = await self.generate_image(
            prompt      = prompt,
            output_path = output_path,
            use_best_model = use_best_model,
            **kwargs,
        )
        self._apply_result_to_scene(scene, scene_id, result)

        # Gọi callback sau apply_result để scene dict đã nhất quán với result
        if on_scene_done:
            await on_scene_done(index, result)

        # Delay sau mọi scene trừ scene cuối để tránh rate-limit
        is_last_scene = index == total - 1
        if not is_last_scene and delay_seconds > 0:
            await asyncio.sleep(delay_seconds)

    def _is_scene_already_done(self, scene: dict, scene_id: str) -> bool:
        """Kiểm tra scene đã được xử lý thành công trước đó chưa.

        Args:
            scene: Dict của scene.
            scene_id: ID scene để ghi log.

        Returns:
            True nếu scene đã ``"completed"`` và có thể bỏ qua.
        """
        if scene.get("status", {}).get("image") == _IMAGE_STATUS_COMPLETED:
            logger.info(
                "[%s] Cảnh '%s' đã có ảnh, bỏ qua.",
                self.model_name, scene_id,
            )
            return True
        return False

    def _extract_prompt(self, scene: dict, scene_id: str) -> Optional[str]:
        """Trích xuất và validate image_prompt từ scene.

        Nếu prompt rỗng hoặc thiếu, đánh dấu scene ``"failed"`` và trả về None.

        Args:
            scene: Dict của scene (có thể bị mutate nếu prompt thiếu).
            scene_id: ID scene để ghi log.

        Returns:
            Chuỗi prompt đã strip, hoặc None nếu không hợp lệ.
        """
        prompt = scene.get("image_prompt", "").strip()
        if not prompt:
            logger.warning(
                "[%s] Cảnh '%s' thiếu image_prompt, đánh dấu failed.",
                self.model_name, scene_id,
            )
            _update_scene_status(scene, status=_IMAGE_STATUS_FAILED)
            return None
        return prompt

    def _build_output_path(self, images_dir: Path, scene_id: str) -> Path:
        """Tạo đường dẫn file ảnh đầu ra theo scene_id.

        Đặt tên đồng bộ với audio step (cùng dùng ``scene_filename_index()``):
            "s1"       → "scene_001.png"
            "scene_03" → "scene_003.png"
            "12"       → "scene_012.png"

        Args:
            images_dir: Thư mục đích.
            scene_id: ID cảnh — bất kể format ("scene_01", "1", "act_03"...).

        Returns:
            Path đầy đủ tới file .png.
        """
        index = scene_filename_index(scene_id)
        return images_dir / _SCENE_FILENAME_PATTERN.format(index=index)

    def _apply_result_to_scene(
        self,
        scene: dict,
        scene_id: str,
        result: ImageResult,
    ) -> None:
        """Ghi kết quả ImageResult vào scene dict.

        Args:
            scene: Dict của scene (mutated in-place).
            scene_id: ID cảnh để ghi log.
            result: Kết quả từ ``generate_image()``.
        """
        if result.success:
            _update_scene_status(scene, status=_IMAGE_STATUS_COMPLETED)
            scene.setdefault("paths", {})["image"] = result.saved_path
            logger.info(
                "[%s] ✅ Cảnh '%s' → %s",
                self.model_name, scene_id, result.saved_path,
            )
        else:
            _update_scene_status(scene, status=_IMAGE_STATUS_FAILED)
            logger.error(
                "[%s] ❌ Cảnh '%s' thất bại: %s",
                self.model_name, scene_id, result.error,
            )


# ─────────────────────────────────────────────────────────────────────────────
# MODULE-LEVEL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _update_scene_status(scene: dict, status: str) -> None:
    """Cập nhật scene["status"]["image"] an toàn (tạo key nếu chưa có).

    Args:
        scene: Dict scene cần cập nhật (mutated in-place).
        status: Giá trị status mới (``"completed"``, ``"failed"``, ...).
    """
    scene.setdefault("status", {})["image"] = status