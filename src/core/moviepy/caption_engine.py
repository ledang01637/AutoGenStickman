"""Caption engine — karaoke word-by-word highlight, TikTok style.
Approach: PIL render snapshot cho mỗi từ active → ImageClip.
"""
from __future__ import annotations

import os
import platform
from pathlib import Path
from typing import Final

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy import ImageClip

from ...utils.logger import get_logger

logger = get_logger(__name__)


# ─── Font ─────────────────────────────────────────────────────────────────────
def _get_font_candidates() -> list[str]:
    system = platform.system()
    if system == "Windows":
        return [
            r"C:\Windows\Fonts\arialbd.ttf",
            r"C:\Windows\Fonts\arial.ttf",
        ]
    elif system == "Darwin":
        return ["/System/Library/Fonts/Supplemental/Arial Bold.ttf"]
    else:
        return [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]


def _resolve_font() -> str | None:
    for f in _get_font_candidates():
        if os.path.exists(f):
            logger.info("caption.font_resolved", extra={"font": f})
            return f
    logger.error("caption.NO_UNICODE_FONT_FOUND")
    return None


_FONT_PATH: Final[str | None] = _resolve_font()

# ─── Style ────────────────────────────────────────────────────────────────────
_COLOR_ACTIVE:        Final[tuple] = (255, 255,   0, 255)  # vàng
_COLOR_INACTIVE:      Final[tuple] = (255, 255, 255, 255)  # trắng
_STROKE_COLOR:        Final[tuple] = (  0,   0,   0, 255)  # đen
_STROKE_WIDTH:        Final[int]   = 3
_FONT_SIZE_RATIO:     Final[float] = 0.040
_BOTTOM_OFFSET_RATIO: Final[float] = 0.08   # cách mép dưới 8%
_MAX_WIDTH_RATIO:     Final[float] = 0.88
_WORDS_PER_LINE:      Final[int]   = 5
_LINE_SPACING:        Final[int]   = 8       # px giữa 2 dòng


# ─── Whisper ──────────────────────────────────────────────────────────────────
def _transcribe_words(audio_path: Path) -> list[dict]:
    """faster-whisper → word timestamps. [] nếu fail."""
    try:
        from faster_whisper import WhisperModel

        logger.info("caption.faster_whisper.start")

        # "medium" tốt cho tiếng Việt có dấu chuẩn, "tiny" nếu muốn nhanh hơn nữa
        # download_root cache model vào /app/models để tránh download lại mỗi lần restart
        model = WhisperModel(
            "medium",
            device="cpu",
            compute_type="int8",          # nhẹ nhất, đủ dùng trên CPU
            download_root="/app/models",  # cache model trong volume
        )

        segments, info = model.transcribe(
            str(audio_path),
            language="vi",
            word_timestamps=True,
            vad_filter=True,
            beam_size=5,          
            best_of=5,          
            temperature=0.0,      
            condition_on_previous_text=True, 
            initial_prompt="Đây là nội dung tiếng Việt.", 
        )

        words = []
        for seg in segments:             # segments là generator, phải iterate
            for w in (seg.words or []):
                word_text = w.word.strip()
                if not word_text:
                    continue
                words.append({
                    "word":  word_text,
                    "start": float(w.start),
                    "end":   float(w.end),
                })

        logger.info("caption.faster_whisper.done", extra={"words": len(words)})
        return words

    except ImportError:
        logger.error("caption.faster_whisper.not_installed",
                     extra={"fix": "pip install faster-whisper==1.2.1"})
        return []
    except Exception as exc:
        logger.error("caption.faster_whisper.failed",
                     extra={"error": str(exc)}, exc_info=True)
        return []

def _fallback_word_timing(text: str, duration: float) -> list[dict]:
    """Chia đều duration cho từng từ khi Whisper không có."""
    words = text.strip().split()
    if not words:
        return []
    d = duration / len(words)
    return [
        {"word": w, "start": i * d, "end": (i + 1) * d}
        for i, w in enumerate(words)
    ]


# ─── PIL Render ───────────────────────────────────────────────────────────────

def _load_pil_font(font_size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load PIL font với fallback."""
    if _FONT_PATH:
        try:
            return ImageFont.truetype(_FONT_PATH, font_size)
        except Exception:
            pass
    return ImageFont.load_default()


def _render_stroke_text(
    draw:       ImageDraw.ImageDraw,
    pos:        tuple[float, float],
    text:       str,
    font:       ImageFont.FreeTypeFont,
    fill:       tuple,
    stroke_width: int,
    stroke_color: tuple,
) -> None:
    """Vẽ text với stroke bằng cách vẽ offset nhiều lần."""
    x, y = pos
    # Vẽ stroke (8 hướng)
    for dx in range(-stroke_width, stroke_width + 1):
        for dy in range(-stroke_width, stroke_width + 1):
            if dx == 0 and dy == 0:
                continue
            draw.text((x + dx, y + dy), text, font=font, fill=stroke_color)
    # Vẽ text chính
    draw.text((x, y), text, font=font, fill=fill)

def _get_dynamic_layout(width: int, height: int) -> tuple[int, int, int]:
    """
    Tính toán font size, bottom offset và max width dựa trên tỷ lệ video.
    Trả về: (font_size, bottom_offset, max_width)
    """
    aspect_ratio = width / height

    if aspect_ratio <= 0.6:  
        # Khung hình dọc (ví dụ 9:16 = 0.56) -> TikTok, Shorts, Reels
        # - Tránh UI của Tiktok (thường chiếm 25-30% ở dưới đáy)
        # - Font size dựa theo width để không bị tràn
        font_size = max(22, int(width * 0.08))      # Chữ chiếm 8% chiều rộng
        bottom_offset = int(height * 0.25)          # Cách đáy 25%
        max_width = int(width * 0.85)               # Rộng tối đa 85% màn hình

    elif aspect_ratio >= 1.5: 
        # Khung hình ngang (ví dụ 16:9 = 1.77) -> YouTube, Phim
        # - Chữ nằm sát dưới đáy giống vietsub
        # - Font size dựa theo height
        font_size = max(22, int(height * 0.06))     # Chữ chiếm 6% chiều cao
        bottom_offset = int(height * 0.08)          # Cách đáy 8%
        max_width = int(width * 0.80)

    else:
        # Khung hình vuông hoặc lỡ cỡ (ví dụ 1:1, 4:5) -> Facebook, Instagram Feed
        font_size = max(22, int(width * 0.06))
        bottom_offset = int(height * 0.15)          # Cách đáy 15%
        max_width = int(width * 0.85)

    return font_size, bottom_offset, max_width

def _render_caption_image(
    line_words:    list[dict],
    active_idx:    int,
    font:          ImageFont.FreeTypeFont,
    canvas_width:  int,
    canvas_height: int,
    max_width:     int,
) -> np.ndarray:
    """
    Render PIL snapshot cho 1 từ active.

    - Toàn dòng hiện trên cùng 1 dòng
    - Từ active_idx: màu vàng
    - Còn lại: màu trắng
    - Có stroke đen
    - Trả về numpy array RGBA
    """
    img  = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    words = [w["word"] for w in line_words]

    # ── Tính tổng width của dòng để căn giữa ──────────────────────────────
    space_w = font.getlength(" ")
    word_widths = [font.getlength(w) for w in words]
    total_w = sum(word_widths) + space_w * (len(words) - 1)

    # Scale down nếu quá rộng
    if total_w > max_width:
        scale = max_width / total_w
    else:
        scale = 1.0

    # ── Tính y căn dưới canvas ────────────────────────────────────────────
    # Lấy font metrics
    bbox   = font.getbbox("Ag")
    text_h = bbox[3] - bbox[1]
    y      = canvas_height - text_h - _STROKE_WIDTH - 4

    # ── Vẽ từng từ ────────────────────────────────────────────────────────
    x = (canvas_width - total_w * scale) / 2  # start x để căn giữa

    for i, (word, w_width) in enumerate(zip(words, word_widths)):
        color = _COLOR_ACTIVE if i == active_idx else _COLOR_INACTIVE

        # Nếu scale < 1 cần dùng font nhỏ hơn
        if scale < 0.95:
            scaled_size = max(12, int(font.size * scale))
            f = _load_pil_font(scaled_size)
        else:
            f = font

        _render_stroke_text(
            draw, (x, y), word, f,
            fill=color,
            stroke_width=_STROKE_WIDTH,
            stroke_color=_STROKE_COLOR,
        )

        x += (w_width + space_w) * scale

    return np.array(img)


# ─── Caption clips ────────────────────────────────────────────────────────────
def create_caption_clips(
    text:       str,
    duration:   float,
    video_size: tuple[int, int],
    audio_path: Path | None = None,
) -> list[ImageClip]:

    if not text or duration <= 0:
        return []

    width, height = video_size
    
    # 1. Gọi hàm layout động thay vì dùng hằng số
    font_size, bottom_offset, max_width = _get_dynamic_layout(width, height)
    font = _load_pil_font(font_size)

    # ── Word timestamps ────────────────────────────────────────────────────
    words: list[dict] = []
    if audio_path and audio_path.exists():
        words = _transcribe_words(audio_path)
    if not words:
        words = _fallback_word_timing(text, duration)
    if not words:
        return []

    for w in words:
        w["start"] = min(w["start"], duration)
        w["end"]   = min(w["end"],   duration)

    # 2. Thu gọn canvas_height lại để căn tọa độ chính xác hơn
    # Font size * 1.5 là đủ không gian cho các chữ có đuôi dài như (g, y, p) và stroke
    canvas_height = int(font_size * 1.5) 
    y_pos         = height - bottom_offset - canvas_height

    clips: list[ImageClip] = []

    for i, word_info in enumerate(words):
        word_start = word_info["start"]
        word_end   = word_info["end"]
        word_text  = word_info["word"]

        # ── Đảm bảo không overlap ──
        if i + 1 < len(words):
            word_end = words[i + 1]["start"]
        word_dur = max(0.05, word_end - word_start)

        try:
            # ── Render CHỈ 1 từ ───────────────────────
            img  = Image.new("RGBA", (width, canvas_height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            bbox   = font.getbbox(word_text)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]

            # Scale nếu từ quá dài
            f = font
            if text_w > max_width:
                scale       = max_width / text_w
                scaled_size = max(12, int(font_size * scale))
                f           = _load_pil_font(scaled_size)
                bbox        = f.getbbox(word_text)
                text_w      = bbox[2] - bbox[0]
                text_h      = bbox[3] - bbox[1]

            # Căn giữa chữ vào giữa canvas theo cả trục X và Y
            x = (width - text_w) / 2
            y = (canvas_height - text_h) // 2

            _render_stroke_text(
                draw, (x, y), word_text, f,
                fill         = _COLOR_ACTIVE,
                stroke_width = _STROKE_WIDTH,
                stroke_color = _STROKE_COLOR,
            )

            frame = np.array(img)

            clip = (
                ImageClip(frame, is_mask=False)
                .with_start(word_start)
                .with_duration(word_dur)
                .with_position(("center", y_pos)) 
            )
            clips.append(clip)

        except Exception as exc:
            logger.error(
                "caption.word_clip_failed",
                extra={"word": word_text, "err": str(exc)},
            )

    logger.info("caption.create.done", extra={"clips": len(clips)})
    return clips

# def create_caption_clips(
#     text:       str,
#     duration:   float,
#     video_size: tuple[int, int],
#     audio_path: Path | None = None,
# ) -> list[ImageClip]:

#     if not text or duration <= 0:
#         return []

#     width, height = video_size
#     font_size  = max(22, int(height * _FONT_SIZE_RATIO))
#     max_width  = int(width * _MAX_WIDTH_RATIO)
#     font       = _load_pil_font(font_size)

#     # ── Word timestamps ────────────────────────────────────────────────────
#     words: list[dict] = []
#     if audio_path and audio_path.exists():
#         words = _transcribe_words(audio_path)
#     if not words:
#         words = _fallback_word_timing(text, duration)
#     if not words:
#         return []

#     for w in words:
#         w["start"] = min(w["start"], duration)
#         w["end"]   = min(w["end"],   duration)

#     bottom_offset = int(height * _BOTTOM_OFFSET_RATIO)
#     canvas_height = font_size * 6
#     y_pos         = height - bottom_offset - canvas_height

#     clips: list[ImageClip] = []

#     for i, word_info in enumerate(words):
#         word_start = word_info["start"]
#         word_end   = word_info["end"]
#         word_text  = word_info["word"]

#         # ── Đảm bảo không overlap: end của từ này = start của từ tiếp theo ──
#         if i + 1 < len(words):
#             word_end = words[i + 1]["start"]   # ← KEY FIX
#         word_dur = max(0.05, word_end - word_start)

#         try:
#             # ── Render CHỈ 1 từ, căn giữa màn hình ───────────────────────
#             img  = Image.new("RGBA", (width, canvas_height), (0, 0, 0, 0))
#             draw = ImageDraw.Draw(img)

#             bbox   = font.getbbox(word_text)
#             text_w = bbox[2] - bbox[0]
#             text_h = bbox[3] - bbox[1]

#             # Scale nếu từ quá dài
#             f = font
#             if text_w > max_width:
#                 scale       = max_width / text_w
#                 scaled_size = max(12, int(font_size * scale))
#                 f           = _load_pil_font(scaled_size)
#                 bbox        = f.getbbox(word_text)
#                 text_w      = bbox[2] - bbox[0]
#                 text_h      = bbox[3] - bbox[1]

#             x = (width - text_w) / 2
#             y = (canvas_height - text_h) // 2

#             _render_stroke_text(
#                 draw, (x, y), word_text, f,
#                 fill         = _COLOR_ACTIVE,   # luôn vàng vì đây là từ đang nói
#                 stroke_width = _STROKE_WIDTH,
#                 stroke_color = _STROKE_COLOR,
#             )

#             frame = np.array(img)

#             clip = (
#                 ImageClip(frame, is_mask=False)
#                 .with_start(word_start)
#                 .with_duration(word_dur)
#                 .with_position(("center", y_pos))
#             )
#             clips.append(clip)

#         except Exception as exc:
#             logger.error(
#                 "caption.word_clip_failed",
#                 extra={"word": word_text, "err": str(exc)},
#             )

#     logger.info("caption.create.done", extra={"clips": len(clips)})
#     return clips