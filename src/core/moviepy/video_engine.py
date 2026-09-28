# === src/core/moviepy/video_engine.py — WITH CAPTIONS + ANIMATION ===
"""VideoEngine — MoviePy assembly với captions + Ken Burns + fade transition.

CPU-bound: phải gọi qua asyncio.to_thread từ async context.
Mỗi instance render 1 video tại 1 thời điểm — KHÔNG share giữa coroutines.

POLICY: Audio = SOURCE OF TRUTH cho duration.
        Image clip ALWAYS = audio.duration (không bao giờ cắt audio).
        max_seconds_per_scene CHỈ dùng để DETECTION (log warning).

CAPTION:   TikTok style — chữ vàng viền đen, đáy, chunks 4-6 từ (caption_engine.py).
ANIMATION: Ken Burns pan-zoom (random in/out) + fade qua đen giữa scenes.
           Logic Ken Burns ở animation_engine.py. Bật/tắt qua enable_animation.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Final, Iterator

from moviepy import (
    AudioFileClip,
    ImageClip,
    CompositeVideoClip,
    concatenate_videoclips,
)
from moviepy.video.fx import FadeIn, FadeOut

from .caption_engine import create_caption_clips
from .animation_engine import apply_ken_burns
from ...utils.logger import get_logger

logger = get_logger(__name__)


# FFmpeg encoding settings tối ưu cho stickman content
_FFMPEG_PRESET:  Final[str] = "veryfast"
_FFMPEG_THREADS: Final[int] = 2
_FFMPEG_FPS:     Final[int] = 24
_VIDEO_CODEC:    Final[str] = "libx264"
_AUDIO_CODEC:    Final[str] = "aac"
_AUDIO_BITRATE:  Final[str] = "128k"

# ─── Transition config ───────────────────────────────────────────────────────
# Fade qua đen: mỗi scene fade in từ đen ở đầu + fade out về đen ở cuối.
# KHÔNG đè audio (mỗi scene độc lập, audio nối tiếp tuần tự).
_FADE_DURATION: Final[float] = 0.4   # Thời lượng fade in/out (giây)
# Scene quá ngắn thì fade ngắn lại để không nuốt mất nội dung
_FADE_MIN_SCENE_DURATION: Final[float] = 1.5


@contextmanager
def _safe_clip_chain(
    scenes: list[dict],
    soft_max_seconds: float | None = None,
    enable_captions: bool = True,
    enable_animation: bool = True,
) -> Iterator[list]:
    """Context manager đảm bảo TẤT CẢ clips được close kể cả khi exception.

    Args:
        scenes:           List scene dicts với paths.image + paths.audio + voiceover.
        soft_max_seconds: Ngưỡng cảnh báo cho overrun (DETECTION ONLY).
        enable_captions:  True → render caption từ scene["voiceover"].
        enable_animation: True → Ken Burns pan-zoom + fade transition.

    Yields:
        List of video clips ready to concatenate.
    """
    composite_clips: list = []
    audio_clips:     list = []
    image_clips:     list = []
    caption_clips:   list = []  # Track riêng để close đúng thứ tự

    try:
        for scene_idx, scene in enumerate(scenes):
            scene_id   = scene.get("scene_id", "?")
            img_path   = scene.get("paths", {}).get("image", "")
            audio_path_str = scene.get("paths", {}).get("audio", "")
            voiceover  = scene.get("voiceover", "")

            if not img_path or not audio_path_str:
                logger.warning(
                    "video.scene.skip",
                    extra={"scene_id": scene_id, "reason": "missing_path"},
                )
                continue

            audio_clip = AudioFileClip(audio_path_str)
            audio_clips.append(audio_clip)

            audio_duration = audio_clip.duration

            # Detection cho audio overrun (không cắt)
            if soft_max_seconds is not None and audio_duration > soft_max_seconds:
                logger.warning(
                    "video.scene.audio_overrun",
                    extra={
                        "scene_id":         scene_id,
                        "audio_duration_s": round(audio_duration, 2),
                        "soft_max_s":       soft_max_seconds,
                        "overrun_s":        round(audio_duration - soft_max_seconds, 2),
                    },
                )

            # Image clip ALWAYS match audio duration
            image_clip = ImageClip(img_path).with_duration(audio_duration)
            image_clips.append(image_clip)
            video_size = image_clip.size

            # ★ ANIMATION: Ken Burns pan-zoom (scale-safe cho nền trắng)
            base_layer = image_clip
            if enable_animation:
                base_layer = apply_ken_burns(
                    image_clip=image_clip,
                    duration=audio_duration,
                    video_size=video_size,
                    seed=scene_idx,  # Seed = idx → reproducible, mỗi scene khác nhau
                )

            # ★ CAPTION: Sinh caption clips từ voiceover
            scene_captions: list = []
            if enable_captions and voiceover:
                try:
                    scene_captions = create_caption_clips(
                        text=voiceover,
                        duration=audio_duration,
                        video_size=video_size,
                        audio_path=Path(audio_path_str) if audio_path_str else None,
                    )
                    caption_clips.extend(scene_captions)
                except Exception as exc:  # noqa: BLE001
                    logger.error(
                        "video.scene.caption_failed",
                        extra={"scene_id": scene_id, "error": str(exc)},
                        exc_info=True,
                    )
                    scene_captions = []

            # Caption KHÔNG bị zoom (nằm trên layer riêng, vị trí cố định)
            if scene_captions:
                composite = CompositeVideoClip(
                    [base_layer] + scene_captions,
                    size=video_size,
                ).with_duration(audio_duration)
            else:
                composite = CompositeVideoClip(
                    [base_layer],
                    size=video_size,
                ).with_duration(audio_duration)

            # Chỉ fade nếu scene đủ dài (tránh nuốt nội dung scene ngắn)
            if enable_animation and audio_duration >= _FADE_MIN_SCENE_DURATION:
                fade_dur = min(_FADE_DURATION, audio_duration / 4)
                composite = composite.with_effects([
                    FadeIn(fade_dur),
                    FadeOut(fade_dur),
                ])

            # Gán audio (audio KHÔNG bị ảnh hưởng bởi fade video)
            video_clip = composite.with_audio(audio_clip)
            composite_clips.append(video_clip)

        yield composite_clips

    finally:
        # Close THEO THỨ TỰ NGƯỢC
        for c in composite_clips:
            try:
                c.close()
            except Exception:  # noqa: BLE001
                pass
        for c in caption_clips:
            try:
                c.close()
            except Exception:  # noqa: BLE001
                pass
        for c in image_clips:
            try:
                c.close()
            except Exception:  # noqa: BLE001
                pass
        for c in audio_clips:
            try:
                c.close()
            except Exception:  # noqa: BLE001
                pass


# def render_final_video(
#     scenes_data: list[dict],
#     output_path: Path,
#     *,
#     target_seconds_per_scene: float | None = None,
#     max_seconds_per_scene:    float | None = None,
#     enable_captions:          bool = True,
#     enable_animation:         bool = True,
# ) -> bool:
#     """Ghép scenes thành video cuối cùng với captions + animation.

#     POLICY:
#         - Audio = source of truth cho duration.
#         - Image adapt theo audio.
#         - Captions từ scene["voiceover"] — chunks 4-6 từ, TikTok style.
#         - Animation: Ken Burns pan-zoom + fade qua đen giữa scenes.
#         - max_seconds_per_scene CHỈ dùng để DETECTION (log warning).

#     Args:
#         scenes_data:              List scene dicts với paths + voiceover.
#         output_path:              Đường dẫn MP4 output.
#         target_seconds_per_scene: Hint từ Stage 1 (chưa dùng — reserved).
#         max_seconds_per_scene:    Soft threshold cho cảnh báo overrun.
#         enable_captions:          False để render video không có sub.
#         enable_animation:         False để render video tĩnh (không Ken Burns/fade).

#     Returns:
#         True nếu thành công, False nếu fail.
#     """
#     if not scenes_data:
#         logger.error("video.render.no_scenes")
#         return False



#     output_path.parent.mkdir(parents=True, exist_ok=True)
#     final_video = None

#     try:
#         with _safe_clip_chain(
#             scenes_data,
#             soft_max_seconds=max_seconds_per_scene,
#             enable_captions=enable_captions,
#             enable_animation=enable_animation,
#         ) as clips:
#             if not clips:
#                 logger.error("video.render.no_valid_clips")
#                 return False

#             total_duration = sum(c.duration for c in clips)
#             logger.info(
#                 "video.render.start",
#                 extra={
#                     "num_clips":         len(clips),
#                     "total_duration_s":  round(total_duration, 2),
#                     "captions_enabled":  enable_captions,
#                     "animation_enabled": enable_animation,
#                 },
#             )

#             final_video = concatenate_videoclips(clips, method="compose")

#             final_video.write_videofile(
#                 str(output_path),
#                 fps=_FFMPEG_FPS,
#                 codec=_VIDEO_CODEC,
#                 audio_codec=_AUDIO_CODEC,
#                 audio_bitrate=_AUDIO_BITRATE,
#                 preset=_FFMPEG_PRESET,
#                 threads=_FFMPEG_THREADS,
#                 logger=None,
#                 temp_audiofile=str(output_path.with_suffix(".temp.m4a")),
#                 remove_temp=True,
#             )

#         logger.info(
#             "video.render.ok",
#             extra={
#                 "path":             str(output_path),
#                 "final_duration_s": round(total_duration, 2),
#             },
#         )
#         return True

#     except Exception as exc:  # noqa: BLE001
#         logger.error(
#             "video.render.crash",
#             extra={"error": str(exc), "output": str(output_path)},
#             exc_info=True,
#         )
#         return False

#     finally:
#         if final_video is not None:
#             try:
#                 final_video.close()
#             except Exception:  # noqa: BLE001
#                 pass

def render_final_video(scenes_data, output_path, *, target_seconds_per_scene=None,
                        max_seconds_per_scene=None, enable_captions=True,
                        enable_animation=True):
    """Ghép scenes thành video cuối cùng với captions + animation.
        POLICY:
            - Audio = source of truth cho duration.
            - Image adapt theo audio.
            - Captions từ scene["voiceover"] — chunks 4-6 từ, TikTok style.
            - Animation: Ken Burns pan-zoom + fade qua đen giữa scenes.
            - max_seconds_per_scene CHỈ dùng để DETECTION (log warning).

        Args:
            scenes_data:              List scene dicts với paths + voiceover.
            output_path:              Đường dẫn MP4 output.
            target_seconds_per_scene: Hint từ Stage 1 (chưa dùng — reserved).
            max_seconds_per_scene:    Soft threshold cho cảnh báo overrun.
            enable_captions:          False để render video không có sub.
            enable_animation:         False để render video tĩnh (không Ken Burns/fade).

        Returns:
            True nếu thành công, False nếu fail.
    """
    if not scenes_data:
        logger.error("video.render.no_scenes")
        return False

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = output_path.parent / f"_scene_temp_{output_path.stem}"
    temp_dir.mkdir(exist_ok=True)
    scene_files: list[Path] = []
    final_video = None

    try:
        for idx, scene in enumerate(scenes_data):
            with _safe_clip_chain(
                [scene], soft_max_seconds=max_seconds_per_scene,
                enable_captions=enable_captions, enable_animation=enable_animation,
            ) as clips:
                if not clips:
                    continue
                scene_path = temp_dir / f"scene_{idx:04d}.mp4"
                clips[0].write_videofile(
                    str(scene_path), fps=_FFMPEG_FPS, codec=_VIDEO_CODEC,
                    audio_codec=_AUDIO_CODEC, audio_bitrate=_AUDIO_BITRATE,
                    preset=_FFMPEG_PRESET, threads=_FFMPEG_THREADS, logger=None,
                )
                scene_files.append(scene_path)
            # toàn bộ audio/image/caption clip của scene này đã được .close()
            # ngay tại đây — RAM được giải phóng trước khi qua scene kế tiếp

        if not scene_files:
            logger.error("video.render.no_valid_clips")
            return False

        from moviepy import VideoFileClip
        final_clips = [VideoFileClip(str(p)) for p in scene_files]
        final_video = concatenate_videoclips(final_clips, method="compose")
        final_video.write_videofile(
            str(output_path), fps=_FFMPEG_FPS, codec=_VIDEO_CODEC,
            audio_codec=_AUDIO_CODEC, audio_bitrate=_AUDIO_BITRATE,
            preset=_FFMPEG_PRESET, threads=_FFMPEG_THREADS, logger=None,
            temp_audiofile=str(output_path.with_suffix(".temp.m4a")), remove_temp=True,
        )
        for c in final_clips:
            c.close()
        return True

    except Exception as exc:
        logger.error("video.render.crash", extra={"error": str(exc)}, exc_info=True)
        return False
    finally:
        if final_video is not None:
            try:
                final_video.close()
            except Exception:
                pass
        for p in scene_files:
            p.unlink(missing_ok=True)
        try:
            temp_dir.rmdir()
        except OSError:
            pass