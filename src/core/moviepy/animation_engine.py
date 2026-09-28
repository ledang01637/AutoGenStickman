# === src/core/moviepy/animation_engine.py ===
"""Animation engine — Ken Burns (pan-zoom) effect cho ảnh tĩnh.

Mục tiêu: ảnh stickman tĩnh trở nên sinh động bằng zoom/pan nhẹ theo thời gian.

QUAN TRỌNG — scale-safe cho nền trắng:
    Ảnh stickman nền trắng, nếu zoom out hoặc pan sẽ lộ mép (vùng trống ngoài ảnh).
    → Giải pháp: LUÔN scale ảnh lớn hơn frame (base_scale > 1.0) trước,
      rồi mới zoom/pan trong vùng dư đó. Không bao giờ lộ mép.

Phụ thuộc: MoviePy v2 (resized, with_position, Effect API).
"""
from __future__ import annotations

import random
from typing import Final

from moviepy import ImageClip

from ...utils.logger import get_logger

logger = get_logger(__name__)


# ─── Ken Burns config ────────────────────────────────────────────────────────
# Base scale: ảnh luôn lớn hơn frame để có "dư địa" cho pan/zoom mà không lộ mép.
_BASE_SCALE: Final[float] = 1.15        # Ảnh phóng 115% so với frame
# Mức zoom thay đổi trong scene (từ base → base × (1 + delta))
_ZOOM_DELTA: Final[float] = 0.10        # Zoom thêm/bớt tối đa 10%
# Pan: dịch chuyển tối đa bao nhiêu % chiều frame
_PAN_RANGE: Final[float] = 0.04         # Pan tối đa 4%


def apply_ken_burns(
    image_clip: ImageClip,
    duration: float,
    video_size: tuple[int, int],
    seed: int | None = None,
) -> ImageClip:
    """Áp dụng hiệu ứng Ken Burns (random in/out + pan nhẹ) lên 1 ImageClip.

    Args:
        image_clip: ImageClip gốc (đã set duration).
        duration:   Thời lượng scene (giây).
        video_size: (width, height) của frame output.
        seed:       Seed random để reproducible (None = ngẫu nhiên thật).

    Returns:
        ImageClip mới với resize động + position động theo thời gian.
        Nếu fail → trả về image_clip gốc (fallback an toàn).
    """
    if duration <= 0:
        return image_clip

    rng = random.Random(seed)
    frame_w, frame_h = video_size

    try:
        # ── 1. Quyết định zoom in hay out (random mỗi scene) ─────────────────
        zoom_in = rng.random() < 0.5

        if zoom_in:
            scale_start = _BASE_SCALE
            scale_end   = _BASE_SCALE * (1.0 + _ZOOM_DELTA)
        else:
            scale_start = _BASE_SCALE * (1.0 + _ZOOM_DELTA)
            scale_end   = _BASE_SCALE

        # ── 2. Pan ngẫu nhiên — hướng dịch chuyển ────────────────────────────
        # Pan range tính theo pixel, giới hạn trong vùng dư của base scale
        max_pan_x = frame_w * _PAN_RANGE
        max_pan_y = frame_h * _PAN_RANGE
        pan_dx = rng.uniform(-max_pan_x, max_pan_x)
        pan_dy = rng.uniform(-max_pan_y, max_pan_y)

        # ── 3. Resize function theo thời gian (linear interpolation) ─────────
        def scale_func(t: float) -> float:
            progress = min(1.0, t / duration) if duration > 0 else 0.0
            return scale_start + (scale_end - scale_start) * progress

        # ── 4. Position function — center + pan động ─────────────────────────
        # Ảnh sau resize lớn hơn frame, position âm để center, cộng pan
        def pos_func(t: float):
            progress = min(1.0, t / duration) if duration > 0 else 0.0
            cur_scale = scale_func(t)

            # Kích thước ảnh hiện tại sau scale
            scaled_w = frame_w * cur_scale
            scaled_h = frame_h * cur_scale

            # Vị trí để center ảnh trong frame (offset âm)
            base_x = (frame_w - scaled_w) / 2
            base_y = (frame_h - scaled_h) / 2

            # Thêm pan dịch dần theo progress
            x = base_x + pan_dx * progress
            y = base_y + pan_dy * progress
            return (x, y)

        # ── 5. Apply: resize ảnh động + reposition ───────────────────────────
        # resized() chấp nhận callable t → scale factor
        animated = (
            image_clip
            .resized(scale_func)        # Scale động theo thời gian
            .with_position(pos_func)    # Position động (pan)
        )

        logger.info(
            "animation.ken_burns.applied",
            extra={
                "zoom":        "in" if zoom_in else "out",
                "scale_range": (round(scale_start, 3), round(scale_end, 3)),
                "pan":         (round(pan_dx, 1), round(pan_dy, 1)),
                "duration":    round(duration, 2),
            },
        )
        return animated

    except Exception as exc:  # noqa: BLE001
        # Fallback: nếu Ken Burns fail, trả ảnh gốc (không phá video)
        logger.error(
            "animation.ken_burns.failed",
            extra={"error": str(exc), "error_type": type(exc).__name__},
            exc_info=True,
        )
        return image_clip