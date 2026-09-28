"""
renderer.py — Stickman renderer

Ghép poses.py + props.py → vẽ nhân vật hoàn chỉnh lên ax.

Gồm:
  draw_face()      — vẽ mặt + biểu cảm (7 expressions)
  draw_stickman()  — vẽ toàn thân + face + prop

Expressions (7):
  neutral, happy, sad, surprised, angry, love, scared

Dùng:
  from .renderer import draw_stickman
  arts = draw_stickman(ax, cx=4.5, cy=2.0, scale=1.1,
                       pose="idle", expression="happy",
                       color="#1a1a2e", prop="bowl", t=0.5)
"""

import math
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Arc, FancyBboxPatch

from .poses_old import get_pose, POSE_NAMES
from .props import draw_prop, PROP_NAMES

# ── Constants ─────────────────────────────────────────────────────────────────

STICKMAN_COLOR  = "#1a1a2e"
DEFAULT_SCALE   = 1.10

# Thứ tự vẽ các đoạn xương
BONE_SEGMENTS = [
    ("hip",      "shoulder"),
    ("shoulder", "l_elbow"), ("l_elbow", "l_hand"),
    ("shoulder", "r_elbow"), ("r_elbow", "r_hand"),
    ("hip",      "l_knee"),  ("l_knee",  "l_foot"),
    ("hip",      "r_knee"),  ("r_knee",  "r_foot"),
]

# Prop gắn vào tay phải, prop nhỏ hơn 1 chút so với nhân vật
PROP_SCALE_FACTOR = 0.72


# ── Face ──────────────────────────────────────────────────────────────────────

def draw_face(ax, cx: float, cy: float, r: float,
              expression: str = "neutral",
              color: str = STICKMAN_COLOR,
              z: int = 10) -> list:
    """
    Vẽ mặt stickman tại (cx, cy) với radius r.

    Args:
        ax         : matplotlib Axes
        cx, cy     : tâm đầu (tọa độ thực)
        r          : bán kính đầu (tọa độ thực)
        expression : neutral | happy | sad | surprised | angry | love | scared
        color      : màu nét vẽ
        z          : zorder

    Returns:
        list[artist]
    """
    arts = []
    f = r / 0.28   # scale factor — r=0.28 là baseline của demo_v2

    ey       = cy + 0.045 * f
    el, er   = cx - 0.082 * f, cx + 0.082 * f
    brow_y   = cy + 0.110 * f
    mouth_y  = cy - 0.075 * f

    # ── Mắt ───────────────────────────────────────────────────────────────────
    if expression in ("surprised", "scared"):
        for ex in [el, er]:
            e = mpatches.Circle((ex, ey), 0.042 * f,
                                color=color, fill=True, zorder=z)
            ax.add_patch(e); arts.append(e)
    elif expression == "angry":
        for ex, sg in [(el, 1), (er, -1)]:
            l = ax.plot([ex - 0.04 * f, ex + 0.04 * f],
                        [ey + sg * 0.02 * f, ey - sg * 0.02 * f],
                        "-", color=color, lw=2.2 * f, zorder=z)[0]
            arts.append(l)
    elif expression == "love":
        for ex in [el, er]:
            h = ax.plot([ex], [ey], "v", color="#E91E63",
                        markersize=6 * f, zorder=z)[0]
            arts.append(h)
    else:
        # neutral / happy / sad — mắt dạng gạch đứng
        for ex in [el, er]:
            l = ax.plot([ex, ex], [ey, ey + 0.060 * f],
                        "-", color=color, lw=2.0 * f,
                        solid_capstyle="round", zorder=z)[0]
            arts.append(l)

    # ── Lông mày ──────────────────────────────────────────────────────────────
    if expression == "angry":
        l1 = ax.plot([el - 0.06 * f, el + 0.04 * f],
                     [brow_y + 0.025 * f, brow_y - 0.010 * f],
                     "-", color=color, lw=2.2 * f, zorder=z)[0]
        l2 = ax.plot([er - 0.04 * f, er + 0.06 * f],
                     [brow_y - 0.010 * f, brow_y + 0.025 * f],
                     "-", color=color, lw=2.2 * f, zorder=z)[0]
        arts += [l1, l2]
    elif expression in ("surprised", "scared", "love"):
        for ex in [el, er]:
            l = ax.plot([ex - 0.04 * f, ex + 0.04 * f],
                        [brow_y + 0.020 * f, brow_y + 0.020 * f],
                        "-", color=color, lw=1.8 * f, zorder=z)[0]
            arts.append(l)
    elif expression == "sad":
        l1 = ax.plot([el - 0.06 * f, el + 0.04 * f],
                     [brow_y - 0.010 * f, brow_y + 0.025 * f],
                     "-", color=color, lw=1.8 * f, zorder=z)[0]
        l2 = ax.plot([er - 0.04 * f, er + 0.06 * f],
                     [brow_y + 0.025 * f, brow_y - 0.010 * f],
                     "-", color=color, lw=1.8 * f, zorder=z)[0]
        arts += [l1, l2]
    else:
        # neutral / happy
        for ex in [el, er]:
            l = ax.plot([ex - 0.04 * f, ex + 0.04 * f],
                        [brow_y, brow_y],
                        "-", color=color, lw=1.8 * f, zorder=z)[0]
            arts.append(l)

    # ── Miệng ─────────────────────────────────────────────────────────────────
    if expression == "happy":
        sm = Arc((cx, mouth_y), 0.20 * f, 0.13 * f,
                 angle=0, theta1=200, theta2=340,
                 color=color, lw=2.2 * f, zorder=z)
        ax.add_patch(sm); arts.append(sm)

    elif expression in ("sad", "angry"):
        fr = Arc((cx, mouth_y - 0.08 * f), 0.18 * f, 0.11 * f,
                 angle=0, theta1=20, theta2=160,
                 color=color, lw=2.2 * f, zorder=z)
        ax.add_patch(fr); arts.append(fr)

    elif expression in ("surprised", "scared"):
        o = mpatches.Circle((cx, mouth_y), 0.052 * f,
                            color=color, fill=False, lw=2.2 * f, zorder=z)
        ax.add_patch(o); arts.append(o)

    elif expression == "love":
        sm = Arc((cx, mouth_y), 0.20 * f, 0.15 * f,
                 angle=0, theta1=200, theta2=340,
                 color=color, lw=2.2 * f, zorder=z)
        ax.add_patch(sm); arts.append(sm)
        for ex in [el - 0.01 * f, er + 0.01 * f]:
            bl = mpatches.Circle((ex, cy - 0.008 * f), 0.040 * f,
                                 color="#F48FB1", alpha=0.55, zorder=z - 1)
            ax.add_patch(bl); arts.append(bl)

    else:
        # neutral
        l = ax.plot([cx - 0.09 * f, cx + 0.09 * f],
                    [mouth_y, mouth_y],
                    "-", color=color, lw=1.8 * f,
                    solid_capstyle="round", zorder=z)[0]
        arts.append(l)

    return arts


# ── Stickman ──────────────────────────────────────────────────────────────────

def draw_stickman(
    ax,
    cx: float,
    cy: float,
    scale: float        = DEFAULT_SCALE,
    pose: str           = "idle",
    expression: str     = "neutral",
    color: str          = STICKMAN_COLOR,
    prop: str | None    = None,
    flip: bool          = False,
    t: float            = 0.0,
    z: int              = 8,
    kp_override: dict | None = None,
) -> list:
    """
    Vẽ stickman hoàn chỉnh (thân + mặt + prop tùy chọn).

    Args:
        ax          : matplotlib Axes
        cx, cy      : vị trí hip (hông) — điểm neo nhân vật
        scale       : kích thước nhân vật (CHAR_SCALE từ CanvasCtx)
        pose        : tên pose (xem poses.POSE_NAMES)
        expression  : biểu cảm (neutral|happy|sad|surprised|angry|love|scared)
        color       : màu stickman
        prop        : tên prop gắn vào tay phải (xem props.PROP_NAMES), None = không có
        flip        : True = lật trái/phải (nhân vật quay sang trái)
        t           : thời gian hiện tại (giây) — dùng cho animation pose
        z           : zorder base
        kp_override : keypoints đã lerp từ engine — nếu có thì bỏ qua pose/t,
                      dùng trực tiếp để vẽ. Cho phép pose interpolation mượt.

    Returns:
        list[artist] — tất cả artist được vẽ, caller dùng để clear
    """
    arts = []
    f    = scale
    sgn  = -1 if flip else 1

    # kp_override từ engine (đã lerp + eased) được ưu tiên tuyệt đối.
    # Fallback về get_pose() khi gọi trực tiếp từ code khác (preview, test).
    kp = kp_override if kp_override is not None else get_pose(pose, t)

    def pt(key: str) -> tuple[float, float]:
        dx, dy = kp[key]
        return cx + sgn * dx * f, cy + dy * f

    # ── Thân xương ────────────────────────────────────────────────────────────
    for a, b in BONE_SEGMENTS:
        ax_, ay_ = pt(a)
        bx_, by_ = pt(b)
        l = ax.plot(
            [ax_, bx_], [ay_, by_],
            "-", color=color,
            lw=3.2 * f,
            solid_capstyle="round",
            zorder=z,
        )[0]
        arts.append(l)

    # ── Đầu ───────────────────────────────────────────────────────────────────
    hx, hy = pt("head")
    hr = 0.32 * f
    head = mpatches.Circle(
        (hx, hy), hr,
        facecolor="white", edgecolor=color,
        linewidth=2.8 * f, zorder=z,
    )
    ax.add_patch(head); arts.append(head)

    # ── Mặt ───────────────────────────────────────────────────────────────────
    arts += draw_face(ax, hx, hy, hr,
                      expression=expression, color=color, z=z + 1)

    # ── Prop ──────────────────────────────────────────────────────────────────
    if prop and prop in PROP_NAMES:
        phx, phy = pt("r_hand")
        prop_scale = f * PROP_SCALE_FACTOR
        arts += draw_prop(ax, prop, phx, phy, scale=prop_scale, z=z + 2)

    return arts