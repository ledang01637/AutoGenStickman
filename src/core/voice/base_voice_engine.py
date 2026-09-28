# src/core/voice/base_voice_engine.py
"""
TẦNG 2B — BaseVoiceEngine

Lớp trừu tượng dùng chung cho TẤT CẢ voice-generation engines
(VbeeEngine, ElevenLabsEngine, OpenAITTSEngine, ...).

Cung cấp:
  - SceneDoneCallback  — type alias cho async callback sau mỗi scene.
  - BaseVoiceEngine    — contract generate_voice() + orchestration generate_voices_for_script().

Không chứa: logic HTTP, token limit, content filter, budget.
"""

from __future__ import annotations

import asyncio
from abc import abstractmethod
from pathlib import Path
from typing import Any, Awaitable, Callable, List, Optional

from ..base_ai_engine import BaseEngine, VoiceResult
from ...utils.logger import get_logger
from ...utils.scene_naming import scene_filename_index

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

_VOICE_STATUS_COMPLETED = "completed"
_VOICE_STATUS_FAILED    = "failed"
_SCENE_FILENAME_PATTERN = "scene_{index}.mp3"


# ─────────────────────────────────────────────────────────────────────────────
# TYPE ALIASES
# ─────────────────────────────────────────────────────────────────────────────

# Callback gọi sau khi mỗi scene xong (thành công hay thất bại).
# Signature: async def cb(scene_idx: int, result: VoiceResult) -> None
# Dùng để partial-update DB ngay sau mỗi scene, tránh race condition
# với các task khác cùng ghi render_config.
SceneDoneCallback = Callable[[int, VoiceResult], Awaitable[None]]


# ─────────────────────────────────────────────────────────────────────────────
# ABSTRACT BASE CLASS
# ─────────────────────────────────────────────────────────────────────────────

class BaseVoiceEngine(BaseEngine):
    """Lớp trừu tượng cho voice-generation engines (TTS).

    Mở rộng ``BaseEngine`` với:
    - Contract ``generate_voice()`` trả về ``VoiceResult`` nhất quán.
    - Orchestration ``generate_voices_for_script()`` tái sử dụng cho mọi engine con.

    Subclasses phải implement:
        ``_is_retryable(error)``             — Xác định lỗi nào được retry.
        ``generate_voice(text, output_path)`` — Tổng hợp một đoạn audio.

    Example::

        class VbeeEngine(BaseVoiceEngine):
            def _is_retryable(self, error):
                return isinstance(error, VbeeTransientError)

            async def generate_voice(self, text, output_path, **kwargs):
                ...

        class ElevenLabsEngine(BaseVoiceEngine):
            def _is_retryable(self, error):
                return isinstance(error, ElevenLabsTransientError)

            async def generate_voice(self, text, output_path, **kwargs):
                ...
    """

    def __init__(self, model_name: str, env_var: str, **kwargs: Any) -> None:
        super().__init__(model_name=model_name, env_var=env_var, **kwargs)

    # ── Abstract contract ─────────────────────────────────────────────────────

    @abstractmethod
    async def generate_voice(
        self,
        text: str,
        output_path: str | Path,
        **kwargs: Any,
    ) -> VoiceResult:
        """Tổng hợp giọng nói từ text và lưu file audio vào output_path.

        Contract bắt buộc cho mọi subclass:
        - KHÔNG raise Exception khi provider từ chối / không tạo được audio.
        - Trả về ``VoiceResult(success=False, error=<lý do>)`` thay thế.
        - Chỉ raise khi gặp lỗi hạ tầng không thể phục hồi (disk full, ...).

        Args:
            text:        Văn bản cần đọc.
            output_path: Đường dẫn file đầu ra (.mp3). Thư mục cha tự động tạo.
            **kwargs:    Thông số tuỳ engine (voice_code, speed, voice_id, ...).

        Returns:
            ``VoiceResult(success=True, saved_path=...)`` nếu thành công,
            ``VoiceResult(success=False, error=...)``     nếu thất bại.
        """

    # ── Orchestration ─────────────────────────────────────────────────────────

    async def generate_voices_for_script(
        self,
        scenes: List[dict],
        audios_dir: str | Path,
        delay_seconds: float = 1.0,
        on_scene_done: Optional[SceneDoneCallback] = None,
        **kwargs: Any,
    ) -> List[dict]:
        """Tổng hợp audio cho toàn bộ danh sách scene (tuần tự, có delay).

        Cập nhật ``scene["status"]["audio"]`` và ``scene["paths"]["audio"]``
        trực tiếp trên từng dict (in-place mutation).

        Idempotent: scene đã ``"completed"`` bị bỏ qua (hỗ trợ pipeline resume).

        Args:
            scenes:        List scene dict từ ``ClaudeEngine.generate_video_script()``.
                           Mỗi scene cần có ``scene_id`` và ``voiceover``.
            audios_dir:    Thư mục lưu file audio (tạo tự động nếu chưa có).
            delay_seconds: Giây nghỉ giữa mỗi API call để tránh rate-limit.
                           Đặt ``0.0`` cho testing.
            on_scene_done: Async callback ``(scene_idx, result)`` sau mỗi scene.
            **kwargs:      Forward tới ``generate_voice()`` (voice_code, speed, ...).

        Returns:
            Danh sách ``scenes`` gốc đã được cập nhật paths + status in-place.
        """
        audios_dir = Path(audios_dir)
        audios_dir.mkdir(parents=True, exist_ok=True)

        total = len(scenes)
        for index, scene in enumerate(scenes):
            await self._process_single_scene(
                scene         = scene,
                index         = index,
                total         = total,
                audios_dir    = audios_dir,
                delay_seconds = delay_seconds,
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
        audios_dir: Path,
        delay_seconds: float,
        on_scene_done: Optional[SceneDoneCallback] = None,
        **kwargs: Any,
    ) -> None:
        """Validate → generate → update scene dict → callback → delay."""
        scene_id = scene.get("scene_id", str(index + 1))

        if self._is_scene_already_done(scene, scene_id):
            return

        text = self._extract_voiceover(scene, scene_id)
        if text is None:
            # _extract_voiceover đã set status="failed" trong scene dict.
            # Gọi callback ngay để DB được cập nhật, không chờ cuối batch.
            if on_scene_done:
                await on_scene_done(index, VoiceResult(
                    saved_path = None,
                    model_name = self.model_name,
                    text       = "",
                    latency_ms = 0.0,
                    success    = False,
                    error      = "Thiếu voiceover",
                ))
            return

        output_path = self._build_output_path(audios_dir, scene_id)
        logger.info(
            "[%s] [%d/%d] Tổng hợp audio cảnh '%s' → %s",
            self.model_name, index + 1, total, scene_id, output_path.name,
        )

        result = await self.generate_voice(text=text, output_path=output_path, **kwargs)
        self._apply_result_to_scene(scene, scene_id, result)

        # Gọi callback sau apply_result để scene dict đã nhất quán với result
        if on_scene_done:
            await on_scene_done(index, result)

        # Delay sau mọi scene trừ scene cuối
        is_last_scene = index == total - 1
        if not is_last_scene and delay_seconds > 0:
            await asyncio.sleep(delay_seconds)

    def _is_scene_already_done(self, scene: dict, scene_id: str) -> bool:
        if scene.get("status", {}).get("audio") == _VOICE_STATUS_COMPLETED:
            logger.info("[%s] Cảnh '%s' đã có audio, bỏ qua.", self.model_name, scene_id)
            return True
        return False

    def _extract_voiceover(self, scene: dict, scene_id: str) -> Optional[str]:
        """Trích xuất voiceover text. Trả về None và đánh dấu failed nếu rỗng."""
        text = scene.get("voiceover", "").strip()
        if not text:
            logger.warning(
                "[%s] Cảnh '%s' thiếu voiceover, đánh dấu failed.",
                self.model_name, scene_id,
            )
            _update_scene_status(scene, _VOICE_STATUS_FAILED)
            return None
        return text

    def _build_output_path(self, audios_dir: Path, scene_id: str) -> Path:
        """scene_id bất kỳ format → "scene_001.mp3", "scene_012.mp3", ...

        Đồng bộ naming với image step (cùng dùng ``scene_filename_index()``).
        """
        index = scene_filename_index(scene_id)
        return audios_dir / _SCENE_FILENAME_PATTERN.format(index=index)

    def _apply_result_to_scene(
        self,
        scene: dict,
        scene_id: str,
        result: VoiceResult,
    ) -> None:
        """Ghi VoiceResult vào scene dict in-place."""
        if result.success:
            _update_scene_status(scene, _VOICE_STATUS_COMPLETED)
            scene.setdefault("paths", {})["audio"] = result.saved_path
            logger.info("[%s] ✅ Cảnh '%s' → %s", self.model_name, scene_id, result.saved_path)
        else:
            _update_scene_status(scene, _VOICE_STATUS_FAILED)
            logger.error("[%s] ❌ Cảnh '%s' thất bại: %s", self.model_name, scene_id, result.error)


# ─────────────────────────────────────────────────────────────────────────────
# MODULE-LEVEL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _update_scene_status(scene: dict, status: str) -> None:
    """Cập nhật scene["status"]["audio"] an toàn (tạo key nếu chưa có)."""
    scene.setdefault("status", {})["audio"] = status