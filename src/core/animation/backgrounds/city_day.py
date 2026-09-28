"""
Background: City Day (Thành phố ban ngày)
Canvas: scale tự động qua CanvasCtx (9:16 / 16:9 / 1:1)

Phù hợp với chủ đề:
  - Đi làm, chen chân giờ cao điểm
  - Cuộc sống đô thị hối hả, stress công việc
  - Mưa đường phố, kẹt xe, trễ giờ
  - Cảm giác lạc lõng giữa đám đông
  - Những khoảnh khắc nhỏ giữa phố thị

Variants:
  morning   — sáng sớm yên tĩnh, bầu trời trong, ít người
  rush_hour — giờ cao điểm, đông đúc, màu sắc sôi động
  rain      — mưa thành phố, bầu trời xám, phản chiếu mặt đường
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch

from .canvas import CanvasCtx
from .utils import (
    setup_ax, gradient_rect, draw_sky, draw_ground,
    draw_sun, draw_moon, draw_clouds, draw_floor_planks,
    draw_tree, draw_stars, draw_storm_clouds, draw_window_grid, draw_rain
)
import math

# ── Palette ───────────────────────────────────────────────────────────────────
SKY_TOP_MORNING   = "#64B5F6"
SKY_BOT_MORNING   = "#B3E5FC"
SKY_TOP_RUSH      = "#1976D2"
SKY_BOT_RUSH      = "#90CAF9"
SKY_TOP_RAIN      = "#546E7A"
SKY_BOT_RAIN      = "#90A4AE"

ROAD_COLOR        = "#424242"
ROAD_DARK         = "#212121"
SIDEWALK_COLOR    = "#9E9E9E"
SIDEWALK_LINE     = "#BDBDBD"
ROAD_LINE_COLOR   = "#FFEE58"   # vạch vàng giữa đường
ROAD_WHITE        = "#F5F5F5"   # vạch trắng zebra

# Tòa nhà
BLDG_COLORS = {
    "morning": ["#90A4AE", "#78909C", "#B0BEC5", "#607D8B", "#CFD8DC"],
    "rush":    ["#546E7A", "#455A64", "#78909C", "#37474F", "#90A4AE"],
    "rain":    ["#455A64", "#37474F", "#546E7A", "#263238", "#607D8B"],
}
BLDG_TOP_ACCENT   = "#B0BEC5"
BLDG_GLASS        = "#29B6F6"

# Cửa sổ
WIN_LIT_MORNING   = "#FFF9C4"
WIN_LIT_RUSH      = "#FFEB3B"
WIN_DARK          = "#1A237E"
WIN_GLASS         = "#B3E5FC"
WIN_RAIN_LIT      = "#FFD54F"

# Đèn đường
LAMP_POST_C       = "#37474F"
LAMP_GLOW_C       = "#FFF9C4"

# Vỉa hè / chi tiết
TREE_TRUNK        = "#5D4037"
TREE_LEAF_MORN    = "#43A047"
TREE_LEAF_RUSH    = "#2E7D32"
TREE_LEAF_RAIN    = "#33691E"

PUDDLE_COLOR      = "#78909C"
PUDDLE_SHIMMER    = "#B0BEC5"

BILLBOARD_BG      = ["#E53935", "#1565C0", "#F57F17"]
SIGN_GREEN        = "#2E7D32"


def build_background_city_day(ax, ctx: CanvasCtx, variant: str = "morning"):
    """
    Vẽ background thành phố ban ngày.

    Args:
        ax      : matplotlib Axes
        ctx     : CanvasCtx — xác định canvas ratio + helpers
        variant : "morning" | "rush_hour" | "rain"
    """
    patches = []
    setup_ax(ax, ctx)
    np.random.seed(42)

    is_morning = variant == "morning"
    is_rush    = variant == "rush_hour"
    is_rain    = variant == "rain"

    # ── Bầu trời gradient ─────────────────────────────────────────────────────
    if is_morning:
        gradient_rect(ax, patches, SKY_TOP_MORNING, SKY_BOT_MORNING,
                      y_bot=ctx.sky_bot, y_top=ctx.sky_top,
                      width=ctx.W, steps=28, zorder=0)
        draw_sun(ax, patches, ctx, nx=0.80, ny=0.90,
                 color="#FFD54F", glow_color="#FFEE58", zorder=2)
        draw_clouds(ax, patches, ctx, n=3, color="white",
                    alpha=0.80, seed=11, zorder=3)
    elif is_rush:
        gradient_rect(ax, patches, SKY_TOP_RUSH, SKY_BOT_RUSH,
                      y_bot=ctx.sky_bot, y_top=ctx.sky_top,
                      width=ctx.W, steps=28, zorder=0)
        draw_sun(ax, patches, ctx, nx=0.72, ny=0.88,
                 color="#FDD835", glow_color="#FFEE58", zorder=2)
        draw_clouds(ax, patches, ctx, n=5, color="white",
                    alpha=0.65, seed=22, zorder=3)
    else:  # rain
        gradient_rect(ax, patches, SKY_TOP_RAIN, SKY_BOT_RAIN,
                      y_bot=ctx.sky_bot, y_top=ctx.sky_top,
                      width=ctx.W, steps=28, zorder=0)
        draw_storm_clouds(ax, patches, ctx, n=7, seed=33, zorder=3)

    # ── Tòa nhà nền (xa, nhỏ) ─────────────────────────────────────────────────
    _draw_buildings_bg(ax, patches, ctx, variant=variant)

    # ── Tòa nhà foreground (gần, to) ──────────────────────────────────────────
    _draw_buildings_fg(ax, patches, ctx, variant=variant)

    # ── Đường + vỉa hè ────────────────────────────────────────────────────────
    _draw_road(ax, patches, ctx, variant=variant)

    # ── Cây đường phố ─────────────────────────────────────────────────────────
    leaf_c = TREE_LEAF_RAIN if is_rain else (TREE_LEAF_RUSH if is_rush else TREE_LEAF_MORN)
    _draw_street_trees(ax, patches, ctx, leaf_color=leaf_c)

    # ── Đèn đường ─────────────────────────────────────────────────────────────
    _draw_street_lamps(ax, patches, ctx, variant=variant)

    # ── Bảng hiệu / billboard ─────────────────────────────────────────────────
    _draw_billboard(ax, patches, ctx, variant=variant)

    # ── Mưa ───────────────────────────────────────────────────────────────────
    if is_rain:
        draw_rain(ax, patches, ctx, n=70, seed=55,
                  color="#90CAF9", zorder=9)
        _draw_puddles(ax, patches, ctx)
        # Overlay mưa tối
        rain_overlay = mpatches.Rectangle(
            (0, 0), ctx.W, ctx.H,
            color="#263238", alpha=0.18, zorder=8
        )
        ax.add_patch(rain_overlay); patches.append(rain_overlay)

    return patches


# ── Helpers ───────────────────────────────────────────────────────────────────

def _draw_buildings_bg(ax, patches, ctx: CanvasCtx, variant: str):
    """
    Tòa nhà nền — nhỏ, mờ, phía xa (mid zone trên).
    Zorder thấp để bị tòa nhà fg che.
    """
    np.random.seed(10)
    rng = np.random

    bldg_cols = BLDG_COLORS.get(
        "rain" if variant == "rain" else ("rush" if variant == "rush_hour" else "morning")
    )

    n_bldg = 8
    total_w = ctx.W
    seg_w = total_w / n_bldg

    for i in range(n_bldg):
        bw = seg_w * rng.uniform(0.65, 0.95)
        bh = ctx.zone_h("mid") * rng.uniform(0.42, 0.82)
        bx = i * seg_w + (seg_w - bw) / 2
        by = ctx.mid_bot + ctx.zone_h("mid") * rng.uniform(0.08, 0.20)
        bc = bldg_cols[i % len(bldg_cols)]

        # Thân tòa nhà
        bldg = mpatches.Rectangle(
            (bx, by), bw, bh,
            color=bc, alpha=0.70, zorder=3
        )
        ax.add_patch(bldg); patches.append(bldg)

        # Mái / viền trên
        roof = mpatches.Rectangle(
            (bx, by + bh), bw, ctx.r(0.012),
            color=BLDG_TOP_ACCENT, alpha=0.50, zorder=3
        )
        ax.add_patch(roof); patches.append(roof)

        # Cửa sổ lưới nhỏ (bg nên ít chi tiết)
        if bw > ctx.r(0.08) and bh > ctx.r(0.12):
            _win_color = lambda: (
                WIN_LIT_MORNING if (variant == "morning" and rng.random() > 0.6)
                else WIN_GLASS if (variant != "rain" and rng.random() > 0.5)
                else WIN_DARK
            )
            draw_window_grid(ax, patches, ctx,
                             bx, by, bw, bh,
                             win_color_fn=_win_color,
                             zorder=4)


def _draw_buildings_fg(ax, patches, ctx: CanvasCtx, variant: str):
    """
    Tòa nhà foreground — 2 tòa hai bên, cắt vào frame.
    Tạo cảm giác chiều sâu đường phố.
    """
    np.random.seed(20)
    rng = np.random

    bldg_cols = BLDG_COLORS.get(
        "rain" if variant == "rain" else ("rush" if variant == "rush_hour" else "morning")
    )
    is_rain = variant == "rain"
    is_rush = variant == "rush_hour"

    # Tòa trái — chiếm ~35% width, cao
    left_w  = ctx.W * 0.32
    left_h  = ctx.zone_h("mid") * 0.90
    left_x  = 0
    left_y  = ctx.mid_bot

    left_bldg = mpatches.Rectangle(
        (left_x, left_y), left_w, left_h,
        color=bldg_cols[1], zorder=5
    )
    ax.add_patch(left_bldg); patches.append(left_bldg)

    # Kính / sọc dọc tòa trái
    for i in range(3):
        stripe_x = left_x + left_w * (0.20 + i * 0.28)
        stripe = mpatches.Rectangle(
            (stripe_x, left_y + left_h * 0.05),
            left_w * 0.08, left_h * 0.88,
            color=BLDG_GLASS, alpha=0.18, zorder=6
        )
        ax.add_patch(stripe); patches.append(stripe)

    # Cửa sổ tòa trái
    def win_left():
        if is_rain:
            return WIN_RAIN_LIT if rng.random() > 0.55 else WIN_DARK
        return WIN_LIT_RUSH if (is_rush and rng.random() > 0.40) else WIN_GLASS

    draw_window_grid(ax, patches, ctx,
                     left_x, left_y, left_w, left_h,
                     win_color_fn=win_left,
                     col=3, row=7, zorder=6)

    # Tòa phải — chiếm ~30% width
    right_w = ctx.W * 0.28
    right_h = ctx.zone_h("mid") * 0.75
    right_x = ctx.W - right_w
    right_y = ctx.mid_bot

    right_bldg = mpatches.Rectangle(
        (right_x, right_y), right_w, right_h,
        color=bldg_cols[3], zorder=5
    )
    ax.add_patch(right_bldg); patches.append(right_bldg)

    # Cửa sổ tòa phải
    def win_right():
        if is_rain:
            return WIN_RAIN_LIT if rng.random() > 0.60 else WIN_DARK
        return WIN_LIT_MORNING if (is_morning := variant == "morning") and rng.random() > 0.55 \
               else WIN_GLASS

    draw_window_grid(ax, patches, ctx,
                     right_x, right_y, right_w, right_h,
                     win_color_fn=win_right,
                     col=3, row=6, zorder=6)

    # Viền trên tòa nhà fg
    for (bx, by, bw, bh) in [
        (left_x,  left_y,  left_w,  left_h),
        (right_x, right_y, right_w, right_h),
    ]:
        top_trim = mpatches.Rectangle(
            (bx, by + bh), bw, ctx.r(0.016),
            color=BLDG_TOP_ACCENT, alpha=0.65, zorder=6
        )
        ax.add_patch(top_trim); patches.append(top_trim)


def _draw_road(ax, patches, ctx: CanvasCtx, variant: str):
    """Mặt đường + vỉa hè + vạch kẻ."""
    is_rain = variant == "rain"

    # Vỉa hè hai bên
    sw = ctx.W * 0.18   # sidewalk width
    for sx in [0, ctx.W - sw]:
        sidewalk = mpatches.Rectangle(
            (sx, 0), sw, ctx.ground_top,
            color=SIDEWALK_COLOR, zorder=2
        )
        ax.add_patch(sidewalk); patches.append(sidewalk)

        # Gạch vỉa hè (vạch ngang)
        for i in range(1, 5):
            gy = ctx.ground_top * i / 5
            gl = ax.plot(
                [sx, sx + sw], [gy, gy],
                '-', color=SIDEWALK_LINE,
                lw=ctx.lw(0.006), alpha=0.40, zorder=2
            )[0]
            patches.append(gl)

    # Mặt đường chính (giữa)
    road_x = sw
    road_w = ctx.W - 2 * sw
    road = mpatches.Rectangle(
        (road_x, 0), road_w, ctx.ground_top,
        color=ROAD_COLOR, zorder=2
    )
    ax.add_patch(road); patches.append(road)

    # Đường phản chiếu mưa
    if is_rain:
        reflect = mpatches.Rectangle(
            (road_x, 0), road_w, ctx.ground_top * 0.30,
            color="#546E7A", alpha=0.35, zorder=3
        )
        ax.add_patch(reflect); patches.append(reflect)

    # Vạch vàng giữa đường (đứt đoạn)
    mid_x = ctx.W / 2
    dash_h = ctx.ground_top * 0.09
    gap_h  = ctx.ground_top * 0.07
    y = ctx.ground_top * 0.05
    while y < ctx.ground_top * 0.88:
        dash = mpatches.Rectangle(
            (mid_x - ctx.r(0.006), y),
            ctx.r(0.012), dash_h,
            color=ROAD_LINE_COLOR, zorder=3
        )
        ax.add_patch(dash); patches.append(dash)
        y += dash_h + gap_h

    # Vạch trắng vỉa hè (zebra crossing) — rush_hour / morning
    if variant != "rain":
        zc_y = ctx.ground_top * 0.68
        zc_h = ctx.ground_top * 0.18
        zc_x = road_x + road_w * 0.30
        for i in range(6):
            stripe = mpatches.Rectangle(
                (zc_x + i * ctx.r(0.022), zc_y),
                ctx.r(0.013), zc_h,
                color=ROAD_WHITE, alpha=0.80, zorder=3
            )
            ax.add_patch(stripe); patches.append(stripe)


def _draw_street_trees(ax, patches, ctx: CanvasCtx, leaf_color: str):
    """Cây lề đường hai bên vỉa hè."""
    sw = ctx.W * 0.18
    tree_positions = [
        # (nx, scale) — nằm trên vỉa hè
        (sw / 2 / ctx.W,          0.78),
        (sw / 2 / ctx.W + 0.005,  0.68),
        ((ctx.W - sw / 2) / ctx.W, 0.75),
    ]
    for nx, scale in tree_positions:
        cx = ctx.x(nx)
        tw = ctx.r(0.014) * scale
        th = ctx.r(0.070) * scale
        lr = ctx.r(0.042) * scale

        # Thân
        trunk = mpatches.Rectangle(
            (cx - tw / 2, ctx.ground_top),
            tw, th,
            color=TREE_TRUNK, zorder=5
        )
        ax.add_patch(trunk); patches.append(trunk)

        # Tán lá — compact hơn cây công viên (đô thị)
        leaf_top = ctx.ground_top + th
        for lx, ly, ldr in [
            (cx,        leaf_top + lr * 0.80, 1.00),
            (cx - lr*0.55, leaf_top + lr * 0.45, 0.65),
            (cx + lr*0.55, leaf_top + lr * 0.42, 0.60),
            (cx - lr*0.20, leaf_top + lr * 1.15, 0.50),
            (cx + lr*0.18, leaf_top + lr * 1.10, 0.46),
        ]:
            lf = plt.Circle((lx, ly), lr * ldr,
                             color=leaf_color, alpha=0.90, zorder=6)
            ax.add_patch(lf); patches.append(lf)


def _draw_street_lamps(ax, patches, ctx: CanvasCtx, variant: str):
    """Cột đèn đường hai bên."""
    is_rain = variant == "rain"
    lamp_positions = [ctx.x(0.17), ctx.x(0.83)]

    for cx in lamp_positions:
        base_y = ctx.ground_top

        # Cột
        pole_h = ctx.zone_h("mid") * 0.55
        pole = mpatches.Rectangle(
            (cx - ctx.r(0.008), base_y),
            ctx.r(0.016), pole_h,
            color=LAMP_POST_C, zorder=6
        )
        ax.add_patch(pole); patches.append(pole)

        # Đế cột
        base = FancyBboxPatch(
            (cx - ctx.r(0.018), base_y - ctx.r(0.008)),
            ctx.r(0.036), ctx.r(0.012),
            boxstyle="round,pad=0.002",
            color=LAMP_POST_C, zorder=6
        )
        ax.add_patch(base); patches.append(base)

        # Cần ngang + chụp đèn
        arm_x  = cx + (ctx.r(0.04) if cx < ctx.W / 2 else -ctx.r(0.04))
        top_y  = base_y + pole_h
        arm = ax.plot(
            [cx, arm_x],
            [top_y, top_y + ctx.r(0.018)],
            '-', color=LAMP_POST_C,
            lw=ctx.lw(0.016), zorder=6
        )[0]
        patches.append(arm)

        shade_w = ctx.r(0.050)
        shade = FancyBboxPatch(
            (arm_x - shade_w / 2, top_y + ctx.r(0.018)),
            shade_w, ctx.r(0.025),
            boxstyle="round,pad=0.004",
            color=LAMP_POST_C, zorder=7
        )
        ax.add_patch(shade); patches.append(shade)

        # Bóng đèn
        bulb = plt.Circle(
            (arm_x, top_y + ctx.r(0.030)),
            ctx.r(0.012),
            color=LAMP_GLOW_C, alpha=0.95, zorder=8
        )
        ax.add_patch(bulb); patches.append(bulb)

        # Glow — luôn sáng khi mưa, mờ khi ban ngày
        glow_alpha = 0.22 if is_rain else 0.08
        glow = plt.Circle(
            (arm_x, top_y + ctx.r(0.030)),
            ctx.r(0.055),
            color=LAMP_GLOW_C, alpha=glow_alpha, zorder=5
        )
        ax.add_patch(glow); patches.append(glow)


def _draw_billboard(ax, patches, ctx: CanvasCtx, variant: str):
    """Bảng hiệu / billboard gắn tường tòa nhà."""
    # Gắn vào tòa nhà bên phải, giữa mid zone
    bw = ctx.r(0.22)
    bh = ctx.r(0.12)
    bx = ctx.W - ctx.W * 0.28 + ctx.r(0.02)
    by = ctx.mid_bot + ctx.zone_h("mid") * 0.38

    # Khung
    frame = FancyBboxPatch(
        (bx - ctx.r(0.006), by - ctx.r(0.006)),
        bw + ctx.r(0.012), bh + ctx.r(0.012),
        boxstyle="round,pad=0.004",
        color="#37474F", zorder=7
    )
    ax.add_patch(frame); patches.append(frame)

    # Nền bảng
    bg_c = BILLBOARD_BG[0] if variant == "morning" else (
           BILLBOARD_BG[1] if variant == "rush_hour" else BILLBOARD_BG[2])
    board = mpatches.Rectangle(
        (bx, by), bw, bh,
        color=bg_c, zorder=8
    )
    ax.add_patch(board); patches.append(board)

    # Chữ đơn giản trên bảng (3 sọc trắng giả chữ)
    for li in range(3):
        line_y = by + bh * (0.25 + li * 0.24)
        line_w = bw * (0.70 if li == 0 else 0.50)
        text_bar = mpatches.Rectangle(
            (bx + (bw - line_w) / 2, line_y),
            line_w, ctx.r(0.010),
            color="#FFFFFF", alpha=0.85, zorder=9
        )
        ax.add_patch(text_bar); patches.append(text_bar)

    # Chân đỡ bảng
    support_x = bx + bw * 0.35
    for sx in [support_x, support_x + bw * 0.30]:
        sup = ax.plot(
            [sx, sx],
            [by - ctx.r(0.025), by],
            '-', color="#37474F",
            lw=ctx.lw(0.014), zorder=7
        )[0]
        patches.append(sup)


def _draw_puddles(ax, patches, ctx: CanvasCtx):
    """Vũng nước trên đường (rain variant)."""
    np.random.seed(77)
    rng = np.random
    sw = ctx.W * 0.18

    puddle_positions = [
        (0.32, 0.25), (0.50, 0.55), (0.62, 0.15),
        (0.44, 0.75), (0.70, 0.40),
    ]
    for nx, ny_frac in puddle_positions:
        px = ctx.x(nx)
        py = ctx.ground_top * ny_frac
        prx = ctx.r(rng.uniform(0.030, 0.060))
        pry = ctx.r(rng.uniform(0.008, 0.016))

        puddle = mpatches.Ellipse(
            (px, py), prx * 2, pry * 2,
            color=PUDDLE_COLOR, alpha=0.55, zorder=3
        )
        ax.add_patch(puddle); patches.append(puddle)

        # Sóng gợn (2 vòng tâm)
        for k in range(1, 3):
            ripple = mpatches.Ellipse(
                (px, py), prx * 2 * (1 + k * 0.22), pry * 2 * (1 + k * 0.22),
                facecolor="none",
                edgecolor=PUDDLE_SHIMMER,
                linewidth=ctx.lw(0.006),
                alpha=0.35 / k, zorder=3
            )
            ax.add_patch(ripple); patches.append(ripple)



def animate_background_city_day(ax, ctx, variant: str, t_sec: float) -> list:
    """
    Dynamic elements thành phố:
    - Mây trôi (morning / rush_hour)
    - Mưa động + đèn đường pulse + vũng nước gợn (rain)
    """
    arts = []

    # ── Mây trôi (morning / rush_hour) ───────────────────────────────────────
    if variant in ("morning", "rush_hour"):
        cloud_a = 0.80 if variant == "morning" else 0.60
        for base_nx, nfy, speed, phase in [(0.12, 0.72, 0.006, 0.0),
                                            (0.45, 0.85, 0.004, 1.5),
                                            (0.78, 0.75, 0.005, 0.8)]:
            nx = (base_nx + t_sec * speed + phase * 0.1) % 1.05
            cx = ctx.x(nx)
            cy = ctx.zone_y("sky", nfy)
            r  = ctx.r(0.042)
            for dx, dy, dr in [(-0.55, 0, 0.40), (0, 0.14, 0.55), (0.55, 0, 0.40)]:
                cl = plt.Circle((cx + dx * r, cy + dy * r), dr * r,
                               color="white", alpha=cloud_a, zorder=3)
                ax.add_patch(cl)
                arts.append(cl)

    # ── Mưa + đèn đường + vũng nước (rain) ───────────────────────────────────
    if variant == "rain":
        # Đèn đường pulse
        for lamp_nx in [0.17, 0.83]:
            arm_x = ctx.x(lamp_nx) + (ctx.r(0.04) if lamp_nx < 0.5 else -ctx.r(0.04))
            top_y = ctx.ground_top + ctx.zone_h("mid") * 0.55 + ctx.r(0.030)
            pulse = 0.20 + math.sin(t_sec * 1.3) * 0.06
            glow  = plt.Circle((arm_x, top_y), ctx.r(0.058),
                               color="#FFF9C4", alpha=pulse, zorder=5)
            ax.add_patch(glow)
            arts.append(glow)

        # Mưa động
        rng = np.random.RandomState(int(t_sec * 15) % 300 + 55)
        for _ in range(35):
            rx  = ctx.x(rng.uniform(0.02, 0.98))
            ny  = ((rng.uniform(0.03, 0.97) + t_sec * 0.08) % 0.97) + 0.03
            rl  = ctx.r(rng.uniform(0.012, 0.024))
            ry  = ctx.y(ny)
            rain = ax.plot([rx, rx - rl * 0.18], [ry, ry - rl],
                           "-", color="#90CAF9", lw=ctx.lw(0.008),
                           alpha=rng.uniform(0.3, 0.6), zorder=9)[0]
            arts.append(rain)

        # Vũng nước gợn
        for nx, ny_frac in [(0.32, 0.25), (0.50, 0.55), (0.62, 0.15)]:
            px    = ctx.x(nx)
            py    = ctx.ground_top * ny_frac
            phase = (t_sec * 0.9 + nx) % 1.0
            scale = 1.0 + phase * 0.5
            ripple = mpatches.Ellipse(
                (px, py), ctx.r(0.042) * 2 * scale, ctx.r(0.012) * 2 * scale,
                facecolor="none", edgecolor="#B0BEC5",
                linewidth=ctx.lw(0.006), alpha=0.30 * (1.0 - phase), zorder=3
            )
            ax.add_patch(ripple)
            arts.append(ripple)

    return arts