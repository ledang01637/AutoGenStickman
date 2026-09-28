"""
stickman_animation_engine.py — Render animation JSON → mp4

Flow:
  render_video(full_json, output_path)
    └─ for each scene:
         ├─ set_background(ax, ctx, bg, variant)   ← 1 lần / scene
         ├─ for each frame:
         │    ├─ eased_alpha = ease_in_out(raw_alpha)
         │    ├─ lerp keypoints giữa pose_prev và pose_next
         │    ├─ draw_stickman(ax, kp_lerped, ...)
         │    ├─ animate_background(ax, ctx, variant, t_sec)
         │    ├─ draw_props / draw_caption
         │    └─ grab_frame → ffmpeg pipe
         └─ next scene

Cải tiến so với v1:
  - Pose lerp thật: lerp_keypoints() thay vì snap ở alpha=0.5
  - Easing: ease_in_out_cubic() cho chuyển động tự nhiên
  - fix render_preview: save_frame() → savefig()
  - Expression blend: cross-fade ở vùng alpha 0.4→0.6
"""

from __future__ import annotations

import logging
import math
import os
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from imageio_ffmpeg import get_ffmpeg_exe
matplotlib.rcParams["animation.ffmpeg_path"] = get_ffmpeg_exe()

from .renderer import draw_stickman
from .poses_old import get_pose, lerp_keypoints, POSE_FN
from .backgrounds.canvas import CanvasCtx
from .backgrounds import BACKGROUND_FN, BACKGROUND_ANIMATE_FN

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

DEFAULT_FPS    = 24
DEFAULT_RATIO  = "9:16"
DPI            = 120
CAPTION_Y_FRAC = 0.08
CAPTION_FONT_SIZE_FRAC = 0.1

ANCHOR_TO_KEYPOINT: dict[str, str] = {
    "right_hand":   "r_hand",
    "left_hand":    "l_hand",
    "above_head":   "head",
    "ground_front": "hip",
    "ground_below": "hip",
    "side_right":   "r_hand",
    "side_left":    "l_hand",
    "front_far":    "hip",
    "body_center":  "shoulder",
}

ANCHOR_OFFSET: dict[str, tuple[float, float]] = {
    "right_hand":   ( 0.0,   0.0),
    "left_hand":    ( 0.0,   0.0),
    "above_head":   ( 0.0,   0.40),
    "ground_front": ( 0.40, -0.92),
    "ground_below": ( 0.0,  -0.92),
    "side_right":   ( 1.20,  0.0),
    "side_left":    (-1.20,  0.0),
    "front_far":    ( 0.60, -0.50),
    "body_center":  ( 0.0,   0.0),
}


# ── Easing ────────────────────────────────────────────────────────────────────

def ease_in_out_cubic(t: float) -> float:
    """
    Cubic ease-in-out: chậm ở đầu, nhanh giữa, chậm ở cuối.

    t=0 → 0, t=1 → 1. Đạo hàm = 0 tại 2 đầu → không giật.
    """
    if t < 0.5:
        return 4 * t * t * t
    p = 2 * t - 2
    return 1 + p * p * p / 2


# ── Keyframe helpers ──────────────────────────────────────────────────────────

def _find_surrounding_keyframes(
    keyframes: list[dict],
    t_ms: float,
) -> tuple[dict, dict, float]:
    """
    Tìm 2 keyframe bao quanh t_ms, trả về alpha tuyến tính thô.
    Caller áp easing lên alpha này.
    """
    if t_ms <= keyframes[0]["t"]:
        return keyframes[0], keyframes[0], 0.0
    if t_ms >= keyframes[-1]["t"]:
        return keyframes[-1], keyframes[-1], 0.0

    for i in range(len(keyframes) - 1):
        a, b = keyframes[i], keyframes[i + 1]
        if a["t"] <= t_ms <= b["t"]:
            span  = b["t"] - a["t"]
            alpha = (t_ms - a["t"]) / span if span > 0 else 0.0
            return a, b, alpha

    return keyframes[-1], keyframes[-1], 0.0


def _get_lerped_pose(
    kf_prev: dict,
    kf_next: dict,
    alpha: float,     # đã qua easing
    t_sec: float,     # thời gian thật — dùng cho micro-animation
) -> dict:
    """
    Lerp keypoints giữa 2 pose theo alpha đã eased.

    Mỗi pose hàm được gọi với t_sec để giữ micro-animation (thở,
    gật đầu, v.v.) — sau đó blend keypoints theo alpha.
    """
    pose_a = kf_prev["pose"]
    pose_b = kf_next["pose"]

    kp_a = get_pose(pose_a, t_sec)
    kp_b = get_pose(pose_b, t_sec)

    return lerp_keypoints(kp_a, kp_b, alpha)


def _blend_expression(
    kf_prev: dict,
    kf_next: dict,
    alpha: float,
) -> str:
    """
    Expression cross-fade ở vùng trung tâm.

    alpha < 0.4  → expression của prev
    0.4–0.6      → transition zone: dùng next để tạo cảm giác đổi nhanh
    alpha > 0.6  → expression của next

    Không lerp màu vì expression là discrete (7 loại), nhưng
    transition zone hẹp hơn snap cứng ở 0.5.
    """
    if alpha < 0.45:
        return kf_prev["expression"]
    return kf_next["expression"]


# ── Caption renderer ──────────────────────────────────────────────────────────

def _draw_caption(ax, ctx: CanvasCtx, text: str, z: int = 20) -> list:
    arts = []
    cx   = ctx.W / 2
    cy   = ctx.H * CAPTION_Y_FRAC
    fs   = ctx.r(CAPTION_FONT_SIZE_FRAC) * 10

    txt = ax.text(
        cx, cy, text,
        ha="center", va="center",
        fontsize=fs,
        fontweight="bold",
        color="white",
        zorder=z + 1,
        wrap=False,
    )
    arts.append(txt)

    fig      = ax.get_figure()
    renderer = fig.canvas.get_renderer()
    try:
        bbox   = txt.get_window_extent(renderer=renderer)
        inv    = ax.transData.inverted()
        bbox_d = bbox.transformed(inv)
        pad_x  = ctx.r(0.06)
        pad_y  = ctx.r(0.018)
        bw = bbox_d.width  + pad_x * 2
        bh = bbox_d.height + pad_y * 2
        bx = cx - bw / 2
        by = cy - bh / 2
    except Exception:
        bw, bh = ctx.r(0.50), ctx.r(0.07)
        bx, by = cx - bw / 2, cy - bh / 2

    bg = mpatches.FancyBboxPatch(
        (bx, by), bw, bh,
        boxstyle="round,pad=0.005",
        facecolor="#000000",
        alpha=0.62,
        zorder=z,
        linewidth=0,
    )
    ax.add_patch(bg)
    arts.insert(0, bg)
    return arts


# ── Prop placement ────────────────────────────────────────────────────────────

def _resolve_prop_position(
    anchor: str,
    cx: float,
    cy: float,
    scale: float,
    flip: bool,
) -> tuple[float, float]:
    dx, dy = ANCHOR_OFFSET.get(anchor, (0.0, 0.0))
    sgn    = -1 if flip else 1
    return cx + sgn * dx * scale, cy + dy * scale


# ── Frame renderer ────────────────────────────────────────────────────────────

class _FrameRenderer:
    """
    Render từng frame. Reuse figure/axes để tránh overhead.
    Background vẽ 1 lần / scene. FG clear + redraw mỗi frame.
    """

    def __init__(self, ctx: CanvasCtx, dpi: int = DPI):
        self.ctx = ctx
        self.dpi = dpi

        self.fig, self.ax = plt.subplots(figsize=(ctx.W, ctx.H), dpi=dpi)
        self.fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
        self.ax.set_xlim(0, ctx.W)
        self.ax.set_ylim(0, ctx.H)
        self.ax.axis("off")
        self.ax.set_aspect("equal")

        self._bg_patches:   list = []
        self._fg_artists:   list = []
        self._anim_artists: list = []
        self._animate_fn         = None
        self._current_variant: str = ""

    def set_background(self, bg_name: str, variant: str) -> None:
        for p in self._bg_patches:
            try:
                p.remove()
            except Exception:
                pass
        self._bg_patches.clear()

        build_fn = BACKGROUND_FN.get(bg_name)
        if build_fn is None:
            logger.warning("Background '%s' không tồn tại, dùng nền trắng.", bg_name)
            self._animate_fn = None
            return

        try:
            self._bg_patches = build_fn(self.ax, self.ctx, variant=variant) or []
        except Exception as e:
            logger.error("Lỗi build background '%s': %s", bg_name, e)

        self._animate_fn       = BACKGROUND_ANIMATE_FN.get(bg_name)
        self._current_variant  = variant

    def _clear_fg(self) -> None:
        for artist in self._fg_artists + self._anim_artists:
            try:
                artist.remove()
            except Exception:
                pass
        self._fg_artists.clear()
        self._anim_artists.clear()

    def render_frame(
        self,
        t_sec:        float,
        kp_lerped:    dict,          # keypoints đã lerp — dùng trực tiếp
        pose_name:    str,           # tên pose hiện tại (cho prop anchor logic)
        expression:   str,
        color:        str,
        cx:           float,
        cy:           float,
        scale:        float,
        flip:         bool,
        active_props: list[dict],
        caption_text: str | None,
        extras_cfg:   list[dict] | None = None,
        t_ms:         float = 0.0,
    ) -> None:
        self._clear_fg()

        # ── Nhân vật chính — dùng kp_lerped đã tính sẵn ─────────────────────
        arts = draw_stickman(
            self.ax,
            cx=cx, cy=cy,
            scale=scale,
            pose=pose_name,       # dùng cho fallback nếu cần
            expression=expression,
            color=color,
            prop=None,
            flip=flip,
            t=t_sec,
            z=8,
            kp_override=kp_lerped,   # truyền kp đã lerp vào renderer
        )
        self._fg_artists.extend(arts)

        # ── Props ─────────────────────────────────────────────────────────────
        from .props import draw_prop
        for prop_cfg in active_props:
            anchor   = prop_cfg.get("anchor", "right_hand")
            px, py   = _resolve_prop_position(anchor, cx, cy, scale, flip)
            prop_arts = draw_prop(self.ax, prop_cfg["shape"], px, py,
                                  scale=scale * 0.72, z=10)
            self._fg_artists.extend(prop_arts)

        # ── Extras (nhân vật phụ) ─────────────────────────────────────────────
        for extra in (extras_cfg or []):
            ekfs = extra.get("keyframes", [])
            if not ekfs:
                continue

            ekf_prev, ekf_next, e_alpha_raw = _find_surrounding_keyframes(ekfs, t_ms)
            e_alpha      = ease_in_out_cubic(e_alpha_raw)
            e_kp_lerped  = _get_lerped_pose(ekf_prev, ekf_next, e_alpha, t_sec)
            e_expr        = _blend_expression(ekf_prev, ekf_next, e_alpha)

            e_x_norm = ekf_prev.get("x", extra.get("x_default", 0.5))
            e_cx     = self.ctx.x(e_x_norm)
            e_arts   = draw_stickman(
                self.ax,
                cx=e_cx, cy=self.ctx.char_y,
                scale=scale,
                pose=ekf_prev["pose"],
                expression=e_expr,
                color=extra.get("color", color),
                prop=None,
                flip=extra.get("flip", False),
                t=t_sec,
                z=8,
                kp_override=e_kp_lerped,
            )
            self._fg_artists.extend(e_arts)

        # ── Dynamic background ────────────────────────────────────────────────
        if self._animate_fn is not None:
            try:
                self._anim_artists = self._animate_fn(
                    self.ax, self.ctx, self._current_variant, t_sec
                ) or []
            except Exception as e:
                logger.warning("animate_bg failed: %s", e)
                self._anim_artists = []

        # ── Caption ───────────────────────────────────────────────────────────
        if caption_text:
            self._fg_artists.extend(_draw_caption(self.ax, self.ctx, caption_text))

    def save_frame(self, path: str) -> None:
        """Lưu frame hiện tại ra PNG."""
        self.fig.savefig(path, dpi=self.dpi, bbox_inches=None, pad_inches=0)

    def close(self) -> None:
        plt.close(self.fig)


# ── FFmpeg pipe renderer ──────────────────────────────────────────────────────

def _render_all_scenes_pipe(
    scenes:      list[dict],
    output_path: str,
    ctx:         CanvasCtx,
    fps:         int,
    char_cfg:    dict,
    dpi:         int = DPI,
) -> None:
    from matplotlib.animation import FFMpegWriter

    color  = char_cfg.get("color", "#1a1a2e")
    flip   = char_cfg.get("flip", False)
    cy     = ctx.char_y
    scale  = ctx.char_scale * char_cfg.get("scale", 1.0)

    writer = FFMpegWriter(
        fps=fps,
        codec="libx264",
        extra_args=["-crf", "23", "-preset", "fast", "-pix_fmt", "yuv420p"],
    )

    fr = _FrameRenderer(ctx, dpi=dpi)
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    with writer.saving(fr.fig, output_path, dpi=dpi):
        for scene in scenes:
            duration_ms = scene["duration_ms"]
            n_frames    = max(1, round(duration_ms / 1000 * fps))
            keyframes   = scene["keyframes"]
            props_cfg   = scene.get("props", [])
            captions    = scene.get("captions", [])
            extras_cfg  = scene.get("extras", [])
            bg_name     = scene["background"]
            variant     = scene["background_variant"]

            fr.set_background(bg_name, variant)

            for fi in range(n_frames):
                t_ms  = fi / fps * 1000
                t_sec = fi / fps

                kf_prev, kf_next, alpha_raw = _find_surrounding_keyframes(keyframes, t_ms)
                alpha      = ease_in_out_cubic(alpha_raw)
                kp_lerped  = _get_lerped_pose(kf_prev, kf_next, alpha, t_sec)
                expression = _blend_expression(kf_prev, kf_next, alpha)

                # Lerp vị trí x từ keyframe — nhân vật di chuyển ngang màn hình
                x_prev = kf_prev.get("x", 0.5)
                x_next = kf_next.get("x", x_prev)
                x_norm = x_prev + (x_next - x_prev) * alpha
                cx     = ctx.x(x_norm)

                active_props = [p for p in props_cfg if p.get("appear_at", 0) <= t_ms]

                caption_text = None
                for cap in captions:
                    if cap["t"] <= t_ms < cap["t"] + cap["duration"]:
                        caption_text = cap["text"]
                        break

                fr.render_frame(
                    t_sec=t_sec,
                    kp_lerped=kp_lerped,
                    pose_name=kf_prev["pose"] if alpha < 0.5 else kf_next["pose"],
                    expression=expression,
                    color=color,
                    cx=cx, cy=cy,
                    scale=scale,
                    flip=flip,
                    active_props=active_props,
                    caption_text=caption_text,
                    extras_cfg=extras_cfg,
                    t_ms=t_ms,
                )
                writer.grab_frame()

            logger.info("Scene '%s' → %d frames (bg=%s/%s)",
                        scene.get("scene_id", "?"), n_frames, bg_name, variant)

    fr.close()
    logger.info("render_video done → %s", output_path)


# ── Main engine ───────────────────────────────────────────────────────────────

class StickmanAnimationEngine:

    def __init__(self, dpi: int = DPI):
        self.dpi = dpi

    def render_video(self, full_json: dict, output_path: str) -> str:
        fps      = full_json.get("fps", DEFAULT_FPS)
        ratio    = full_json.get("canvas", {}).get("ratio", DEFAULT_RATIO)
        char_cfg = full_json.get("character", {})
        scenes   = full_json.get("scenes", [])
        ctx      = CanvasCtx(ratio)

        _render_all_scenes_pipe(
            scenes=scenes, output_path=output_path,
            ctx=ctx, fps=fps, char_cfg=char_cfg, dpi=self.dpi,
        )
        return output_path

    def render_preview(
        self,
        full_json:   dict,
        output_path: str,
        scene_index: int = 0,
        at_ms:       int = 0,
    ) -> str:
        fps      = full_json.get("fps", DEFAULT_FPS)
        ratio    = full_json.get("canvas", {}).get("ratio", DEFAULT_RATIO)
        char_cfg = full_json.get("character", {})
        scenes   = full_json.get("scenes", [])

        if scene_index >= len(scenes):
            raise ValueError(f"scene_index={scene_index} vượt quá {len(scenes)} scenes.")

        scene     = scenes[scene_index]
        ctx       = CanvasCtx(ratio)
        keyframes = scene["keyframes"]
        props_cfg = scene.get("props", [])
        captions  = scene.get("captions", [])
        t_sec     = at_ms / 1000

        kf_prev, kf_next, alpha_raw = _find_surrounding_keyframes(keyframes, at_ms)
        alpha      = ease_in_out_cubic(alpha_raw)
        kp_lerped  = _get_lerped_pose(kf_prev, kf_next, alpha, t_sec)
        expression = _blend_expression(kf_prev, kf_next, alpha)

        active_props = [p for p in props_cfg if p.get("appear_at", 0) <= at_ms]
        caption_text = None
        for cap in captions:
            if cap["t"] <= at_ms < cap["t"] + cap["duration"]:
                caption_text = cap["text"]
                break

        fr = _FrameRenderer(ctx, dpi=self.dpi)
        fr.set_background(scene["background"], scene["background_variant"])
        fr.render_frame(
            t_sec=t_sec,
            kp_lerped=kp_lerped,
            pose_name=kf_prev["pose"] if alpha < 0.5 else kf_next["pose"],
            expression=expression,
            color=char_cfg.get("color", "#1a1a2e"),
            cx=ctx.W / 2,
            cy=ctx.char_y,
            scale=ctx.char_scale * char_cfg.get("scale", 1.0),
            flip=char_cfg.get("flip", False),
            active_props=active_props,
            caption_text=caption_text,
        )

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        fr.save_frame(output_path)
        fr.close()
        return output_path