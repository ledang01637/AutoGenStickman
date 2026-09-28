"""
Background: Park Day (Công viên ban ngày)
Canvas: scale tự động qua CanvasCtx (9:16 / 16:9 / 1:1)

Phù hợp với chủ đề:
  - Dạo công viên, xả stress cuối tuần
  - Đọc sách / nghe nhạc ngoài trời
  - Hẹn hò, đi chơi cùng người thân
  - Tản bộ buổi chiều tà
  - Khoảnh khắc yên bình giữa cuộc sống bận rộn

Variants:
  sunny  — ban ngày nắng đẹp, bầu trời xanh, đầy năng lượng
  evening — chiều tà, ánh hoàng hôn vàng cam, lãng mạn
  date   — buổi sáng/chiều lý tưởng, hoa anh đào, ghế băng đôi
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
from .canvas import CanvasCtx
from .utils import (
    setup_ax, gradient_rect, draw_sky, draw_ground,
    draw_sun, draw_moon, draw_clouds, draw_floor_planks,
    draw_tree, draw_stars
)
import math

# ── Palette ───────────────────────────────────────────────────────────────────
SKY_TOP_SUNNY    = "#42A5F5"
SKY_BOT_SUNNY    = "#90CAF9"
SKY_TOP_EVENING  = "#E65100"
SKY_BOT_EVENING  = "#FFF176"
SKY_TOP_DATE     = "#5C6BC0"
SKY_BOT_DATE     = "#CE93D8"

GRASS_SUNNY      = "#4CAF50"
GRASS_DARK_SUNNY = "#388E3C"
GRASS_EVENING    = "#8BC34A"
GRASS_DARK_EVE   = "#558B2F"
GRASS_DATE       = "#66BB6A"
GRASS_DARK_DATE  = "#43A047"

PATH_COLOR       = "#BCAAA4"
PATH_EDGE        = "#A1887F"

BENCH_WOOD       = "#8D6E63"
BENCH_METAL      = "#546E7A"

TREE_TRUNK       = "#5D4037"
LEAF_SUNNY       = "#2E7D32"
LEAF_EVENING     = "#F57F17"
LEAF_DATE        = "#F48FB1"   # hoa anh đào

LAMP_POST        = "#37474F"
LAMP_GLOW        = "#FFF9C4"

FLOWER_COLORS    = ["#F44336", "#E91E63", "#FFEB3B", "#FF9800", "#9C27B0"]
BUSH_GREEN       = "#388E3C"

POND_COLOR       = "#29B6F6"
POND_SHIMMER     = "#B3E5FC"


def build_background_park_day(ax, ctx: CanvasCtx, variant: str = "sunny"):
    """
    Vẽ background công viên ban ngày.

    Args:
        ax      : matplotlib Axes
        ctx     : CanvasCtx — xác định canvas ratio + helpers
        variant : "sunny" | "evening" | "date"
    """
    patches = []
    setup_ax(ax, ctx)
    np.random.seed(42)

    is_sunny   = variant == "sunny"
    is_evening = variant == "evening"
    is_date    = variant == "date"

    # ── Bầu trời gradient ─────────────────────────────────────────────────────
    if is_sunny:
        gradient_rect(ax, patches, SKY_TOP_SUNNY, SKY_BOT_SUNNY,
                      y_bot=ctx.sky_bot, y_top=ctx.sky_top,
                      width=ctx.W, steps=28, zorder=0)
    elif is_evening:
        gradient_rect(ax, patches, SKY_TOP_EVENING, SKY_BOT_EVENING,
                      y_bot=ctx.sky_bot, y_top=ctx.sky_top,
                      width=ctx.W, steps=32, zorder=0)
    else:  # date
        gradient_rect(ax, patches, SKY_TOP_DATE, SKY_BOT_DATE,
                      y_bot=ctx.sky_bot, y_top=ctx.sky_top,
                      width=ctx.W, steps=28, zorder=0)

    # ── Mặt trời / ánh hoàng hôn ──────────────────────────────────────────────
    if is_sunny:
        draw_sun(ax, patches, ctx, nx=0.82, ny=0.94,
                 color="#FFD54F", glow_color="#FFEE58", zorder=2)
        draw_clouds(ax, patches, ctx, n=4, color="white", alpha=0.88,
                    seed=12, zorder=3)
    elif is_evening:
        draw_sun(ax, patches, ctx, nx=0.15, ny=0.78,
                 color="#FF7043", glow_color="#FFAB40", zorder=2)
        draw_clouds(ax, patches, ctx, n=5, color="#FFCCBC",
                    y_frac_range=(0.15, 0.70),
                    alpha=0.75, seed=33, zorder=3)
    else:  # date
        draw_sun(ax, patches, ctx, nx=0.78, ny=0.90,
                 color="#FFB74D", glow_color="#FFE082", zorder=2)
        draw_clouds(ax, patches, ctx, n=3, color="#F8BBD9",
                    alpha=0.70, seed=21, zorder=3)

    # ── Nền cỏ ────────────────────────────────────────────────────────────────
    grass_c = GRASS_EVENING if is_evening else (GRASS_DATE if is_date else GRASS_SUNNY)
    grass_dk = GRASS_DARK_EVE if is_evening else (GRASS_DARK_DATE if is_date else GRASS_DARK_SUNNY)

    grass = mpatches.Rectangle(
        (0, 0), ctx.W, ctx.ground_top,
        color=grass_c, zorder=1
    )
    ax.add_patch(grass); patches.append(grass)

    # Họa tiết cỏ (các vạch ngang)
    _draw_grass_texture(ax, patches, ctx, grass_dk, zorder=2)

    # Vùng cỏ mid zone dưới (phần chân cây, bụi cỏ)
    mid_grass = mpatches.Rectangle(
        (0, ctx.ground_top), ctx.W, ctx.r(0.04),
        color=grass_dk, alpha=0.30, zorder=2
    )
    ax.add_patch(mid_grass); patches.append(mid_grass)

    # ── Con đường công viên ────────────────────────────────────────────────────
    _draw_path(ax, patches, ctx, variant=variant)

    # ── Cây xanh ──────────────────────────────────────────────────────────────
    leaf_c = LEAF_EVENING if is_evening else (LEAF_DATE if is_date else LEAF_SUNNY)
    _draw_trees(ax, patches, ctx, leaf_color=leaf_c, variant=variant)

    # ── Bụi cây / hàng rào xanh ───────────────────────────────────────────────
    _draw_bushes(ax, patches, ctx, variant=variant)

    # ── Ghế băng công viên ────────────────────────────────────────────────────
    _draw_bench(ax, patches, ctx, variant=variant)

    # ── Đèn đường công viên ───────────────────────────────────────────────────
    _draw_lamp_post(ax, patches, ctx, nx=0.82, variant=variant)

    # ── Ao nhỏ (sunny / date) ─────────────────────────────────────────────────
    if is_sunny or is_date:
        _draw_pond(ax, patches, ctx, variant=variant)

    # ── Hoa dọc lối đi (date) ─────────────────────────────────────────────────
    if is_date:
        _draw_flowers(ax, patches, ctx)

    # ── Chim (sunny) ──────────────────────────────────────────────────────────
    if is_sunny:
        _draw_birds(ax, patches, ctx)

    # ── Overlay hoàng hôn ─────────────────────────────────────────────────────
    if is_evening:
        eve_overlay = mpatches.Rectangle(
            (0, 0), ctx.W, ctx.H,
            color="#E65100", alpha=0.08, zorder=8
        )
        ax.add_patch(eve_overlay); patches.append(eve_overlay)

        # Bóng dài của cây (evening)
        _draw_evening_shadows(ax, patches, ctx)

    return patches


# ── Helpers ───────────────────────────────────────────────────────────────────

def _draw_grass_texture(ax, patches, ctx: CanvasCtx,
                         dark_color: str, zorder: int = 2):
    """Vân cỏ — đường ngang nhạt trên nền ground."""
    np.random.seed(77)
    n_lines = 6
    for i in range(1, n_lines + 1):
        y = ctx.ground_top * i / (n_lines + 1)
        l = ax.plot([0, ctx.W], [y, y], '-',
                    color=dark_color,
                    lw=ctx.lw(0.006), alpha=0.30, zorder=zorder)[0]
        patches.append(l)


def _draw_path(ax, patches, ctx: CanvasCtx, variant: str):
    """Con đường uốn lượn qua công viên."""
    # Đường đi từ trái-phải, hơi cong
    path_w = ctx.r(0.28)
    path_y = ctx.ground_top * 0.15
    path_h = ctx.ground_top * 0.55

    # Thân đường
    path = FancyBboxPatch(
        (ctx.x(0.22), path_y),
        ctx.x(0.56), path_h,
        boxstyle="round,pad=0.008",
        color=PATH_COLOR, zorder=3
    )
    ax.add_patch(path); patches.append(path)

    # Viền đường
    path_edge_l = ax.plot(
        [ctx.x(0.22), ctx.x(0.22)],
        [path_y, path_y + path_h],
        '-', color=PATH_EDGE,
        lw=ctx.lw(0.012), alpha=0.60, zorder=4
    )[0]
    patches.append(path_edge_l)

    path_edge_r = ax.plot(
        [ctx.x(0.78), ctx.x(0.78)],
        [path_y, path_y + path_h],
        '-', color=PATH_EDGE,
        lw=ctx.lw(0.012), alpha=0.60, zorder=4
    )[0]
    patches.append(path_edge_r)

    # Vạch giữa đường (đứt đoạn)
    dash_y = path_y + path_h * 0.45
    for i in range(5):
        dx = ctx.x(0.30 + i * 0.085)
        dash = ax.plot(
            [dx, dx + ctx.r(0.032)],
            [dash_y, dash_y],
            '-', color=PATH_EDGE,
            lw=ctx.lw(0.008), alpha=0.35, zorder=4
        )[0]
        patches.append(dash)


def _draw_trees(ax, patches, ctx: CanvasCtx,
                leaf_color: str, variant: str):
    """Hàng cây hai bên lối đi."""
    # Cây trái (xa hơn, nhỏ hơn)
    tree_positions_left = [
        (0.05, 0.80), (0.12, 0.75), (0.18, 0.82),
    ]
    # Cây phải
    tree_positions_right = [
        (0.88, 0.78), (0.80, 0.82), (0.94, 0.74),
    ]

    all_positions = tree_positions_left + tree_positions_right

    for nx, scale in all_positions:
        draw_tree(ax, patches, ctx,
                  nx=nx,
                  y_base=ctx.ground_top,
                  trunk_color=TREE_TRUNK,
                  leaf_color=leaf_color,
                  scale=scale,
                  zorder=5)

    # Cây lớn hơn ở giữa hai bên (foreground)
    if variant == "date":
        # Thêm cây anh đào to hơn ở date
        for nx, scale in [(0.08, 1.10), (0.90, 1.05)]:
            draw_tree(ax, patches, ctx,
                      nx=nx,
                      y_base=ctx.ground_top,
                      trunk_color=TREE_TRUNK,
                      leaf_color=LEAF_DATE,
                      scale=scale,
                      zorder=5)
            # Cánh hoa rơi
            _draw_petals(ax, patches, ctx, cx=ctx.x(nx), zorder=6)
    else:
        for nx, scale in [(0.08, 1.0), (0.91, 0.95)]:
            draw_tree(ax, patches, ctx,
                      nx=nx,
                      y_base=ctx.ground_top,
                      trunk_color=TREE_TRUNK,
                      leaf_color=leaf_color,
                      scale=scale,
                      zorder=5)


def _draw_petals(ax, patches, ctx: CanvasCtx, cx: float, zorder: int = 6):
    """Cánh hoa anh đào rơi."""
    np.random.seed(int(cx * 10))
    rng = np.random
    for _ in range(12):
        px = cx + rng.uniform(-ctx.r(0.30), ctx.r(0.30))
        py = ctx.ground_top + rng.uniform(ctx.r(0.05), ctx.zone_h("mid") * 0.60)
        ps = ctx.r(rng.uniform(0.008, 0.016))
        petal = plt.Circle(
            (px, py), ps,
            color="#F8BBD9", alpha=rng.uniform(0.5, 0.9), zorder=zorder
        )
        ax.add_patch(petal); patches.append(petal)


def _draw_bushes(ax, patches, ctx: CanvasCtx, variant: str):
    """Bụi cây dọc hai bên."""
    bush_c = "#33691E" if variant == "evening" else BUSH_GREEN
    positions = [
        (0.02, 0.85), (0.15, 0.82), (0.83, 0.80), (0.97, 0.78),
    ]
    np.random.seed(88)
    for nx, scale in positions:
        cx = ctx.x(nx)
        cy = ctx.ground_top + ctx.r(0.018)
        r  = ctx.r(0.048 * scale)
        for dx, dy, dr in [
            (-0.5, 0,    0.55),
            (0,    0.30, 0.65),
            (0.5,  0,    0.50),
            (0,   -0.15, 0.40),
        ]:
            bush = plt.Circle(
                (cx + dx * r, cy + dy * r), dr * r,
                color=bush_c, alpha=0.90, zorder=4
            )
            ax.add_patch(bush); patches.append(bush)


def _draw_bench(ax, patches, ctx: CanvasCtx, variant: str):
    """Ghế băng công viên."""
    # date có 2 ghế gần nhau, các variant khác có 1 ghế
    bench_positions = [(0.42, 0.58)] if variant != "date" else [(0.38, 0.54), (0.55, 0.71)]

    for nx_left, nx_right in bench_positions:
        bx = ctx.x(nx_left)
        by = ctx.ground_top * 0.25
        bw = ctx.x(nx_right) - ctx.x(nx_left)
        bh = ctx.r(0.022)

        # Chân ghế
        for leg_x in [bx + bw * 0.12, bx + bw * 0.88]:
            leg = mpatches.Rectangle(
                (leg_x - ctx.r(0.007), by - ctx.r(0.032)),
                ctx.r(0.014), ctx.r(0.035),
                color=BENCH_METAL, zorder=5
            )
            ax.add_patch(leg); patches.append(leg)

        # Mặt ghế
        seat = FancyBboxPatch(
            (bx, by), bw, bh,
            boxstyle="round,pad=0.004",
            color=BENCH_WOOD, zorder=6
        )
        ax.add_patch(seat); patches.append(seat)

        # Lưng ghế
        backrest = FancyBboxPatch(
            (bx, by + bh + ctx.r(0.012)),
            bw, bh * 0.55,
            boxstyle="round,pad=0.003",
            color=BENCH_WOOD, zorder=6
        )
        ax.add_patch(backrest); patches.append(backrest)

        # Thanh dọc lưng ghế
        for sx in [bx + bw * 0.15, bx + bw * 0.50, bx + bw * 0.85]:
            sl = ax.plot(
                [sx, sx],
                [by + bh, by + bh + ctx.r(0.012)],
                '-', color=BENCH_METAL,
                lw=ctx.lw(0.010), zorder=5
            )[0]
            patches.append(sl)


def _draw_lamp_post(ax, patches, ctx: CanvasCtx,
                    nx: float, variant: str):
    """Cột đèn công viên."""
    cx = ctx.x(nx)
    base_y = ctx.ground_top

    # Thân cột
    pole_h = ctx.zone_h("mid") * 0.65
    pole = mpatches.Rectangle(
        (cx - ctx.r(0.010), base_y),
        ctx.r(0.020), pole_h,
        color=LAMP_POST, zorder=5
    )
    ax.add_patch(pole); patches.append(pole)

    # Đế cột
    base = FancyBboxPatch(
        (cx - ctx.r(0.022), base_y - ctx.r(0.010)),
        ctx.r(0.044), ctx.r(0.016),
        boxstyle="round,pad=0.003",
        color=LAMP_POST, zorder=5
    )
    ax.add_patch(base); patches.append(base)

    # Chụp đèn
    top_y = base_y + pole_h
    shade_w = ctx.r(0.060)
    shade_h = ctx.r(0.032)
    shade = FancyBboxPatch(
        (cx - shade_w / 2, top_y),
        shade_w, shade_h,
        boxstyle="round,pad=0.005",
        color=LAMP_POST, zorder=6
    )
    ax.add_patch(shade); patches.append(shade)

    # Bóng đèn
    bulb = plt.Circle(
        (cx, top_y + shade_h * 0.40),
        ctx.r(0.014),
        color=LAMP_GLOW, alpha=0.95, zorder=7
    )
    ax.add_patch(bulb); patches.append(bulb)

    # Glow hào quang (evening)
    if variant == "evening":
        glow = plt.Circle(
            (cx, top_y + shade_h * 0.40),
            ctx.r(0.070),
            color=LAMP_GLOW, alpha=0.15, zorder=4
        )
        ax.add_patch(glow); patches.append(glow)

    # Cần cong
    arm = ax.plot(
        [cx, cx + ctx.r(0.042)],
        [top_y + shade_h, top_y + shade_h + ctx.r(0.010)],
        '-', color=LAMP_POST,
        lw=ctx.lw(0.018), zorder=5
    )[0]
    patches.append(arm)


def _draw_pond(ax, patches, ctx: CanvasCtx, variant: str):
    """Ao nhỏ góc trái."""
    pond_cx = ctx.x(0.18)
    pond_cy = ctx.ground_top * 0.50
    pond_rx = ctx.r(0.12)
    pond_ry = ctx.r(0.045)

    pond = mpatches.Ellipse(
        (pond_cx, pond_cy), pond_rx * 2, pond_ry * 2,
        color=POND_COLOR, alpha=0.82, zorder=3
    )
    ax.add_patch(pond); patches.append(pond)

    # Ánh sáng lấp lánh trên mặt nước
    for i in range(3):
        sx = pond_cx + ctx.r((-0.04 + i * 0.04))
        sy = pond_cy + ctx.r(0.010)
        shimmer = ax.plot(
            [sx - ctx.r(0.014), sx + ctx.r(0.014)],
            [sy, sy],
            '-', color=POND_SHIMMER,
            lw=ctx.lw(0.014), alpha=0.60, zorder=4
        )[0]
        patches.append(shimmer)

    # Viên đá quanh ao
    np.random.seed(66)
    for _ in range(8):
        angle = np.random.uniform(0, 2 * np.pi)
        rx_ = pond_rx + ctx.r(np.random.uniform(0.010, 0.018))
        ry_ = pond_ry + ctx.r(np.random.uniform(0.005, 0.010))
        sx = pond_cx + rx_ * np.cos(angle)
        sy = pond_cy + ry_ * np.sin(angle)
        stone = plt.Circle(
            (sx, sy), ctx.r(np.random.uniform(0.006, 0.012)),
            color="#90A4AE", alpha=0.80, zorder=4
        )
        ax.add_patch(stone); patches.append(stone)

    # Vịt (sunny)
    if variant == "sunny":
        _draw_duck(ax, patches, ctx, cx=pond_cx - ctx.r(0.04), cy=pond_cy)


def _draw_duck(ax, patches, ctx: CanvasCtx,
               cx: float, cy: float):
    """Con vịt đơn giản trên ao."""
    r = ctx.r(0.018)

    # Thân vịt
    body = mpatches.Ellipse(
        (cx, cy), r * 2.2, r * 1.0,
        color="#FFFFFF", zorder=5
    )
    ax.add_patch(body); patches.append(body)

    # Đầu vịt
    head = plt.Circle(
        (cx + r * 1.0, cy + r * 0.40), r * 0.55,
        color="#FFFFFF", zorder=6
    )
    ax.add_patch(head); patches.append(head)

    # Mỏ vịt
    beak = mpatches.Wedge(
        (cx + r * 1.50, cy + r * 0.40), r * 0.28,
        -20, 20, color="#FF8F00", zorder=7
    )
    ax.add_patch(beak); patches.append(beak)

    # Mào xanh lá (đực)
    crest = plt.Circle(
        (cx + r * 0.92, cy + r * 0.72), r * 0.30,
        color="#1B5E20", alpha=0.90, zorder=7
    )
    ax.add_patch(crest); patches.append(crest)


def _draw_flowers(ax, patches, ctx: CanvasCtx):
    """Hàng hoa dọc lối đi (date variant)."""
    positions_x = np.linspace(ctx.x(0.22), ctx.x(0.78), 10)
    flower_y = ctx.ground_top * 0.08
    np.random.seed(44)

    for i, fx in enumerate(positions_x):
        fc = FLOWER_COLORS[i % len(FLOWER_COLORS)]

        # Thân hoa
        stem = ax.plot(
            [fx, fx],
            [0, flower_y],
            '-', color="#388E3C",
            lw=ctx.lw(0.008), zorder=4
        )[0]
        patches.append(stem)

        # Cánh hoa
        for angle in range(0, 360, 60):
            rad = np.deg2rad(angle)
            pr = ctx.r(0.014)
            px = fx + pr * np.cos(rad)
            py = flower_y + pr * np.sin(rad)
            petal = plt.Circle(
                (px, py), ctx.r(0.010),
                color=fc, alpha=0.85, zorder=5
            )
            ax.add_patch(petal); patches.append(petal)

        # Nhụy hoa
        center = plt.Circle(
            (fx, flower_y), ctx.r(0.008),
            color="#FFD54F", zorder=6
        )
        ax.add_patch(center); patches.append(center)


def _draw_birds(ax, patches, ctx: CanvasCtx):
    """Vài con chim đơn giản trên bầu trời (sunny)."""
    np.random.seed(55)
    bird_positions = [
        (0.30, 0.88), (0.45, 0.92), (0.55, 0.90),
        (0.65, 0.86),
    ]
    for nx, nfy in bird_positions:
        bx = ctx.x(nx)
        by = ctx.zone_y("sky", nfy - 0.68)   # map vào sky zone
        size = ctx.r(np.random.uniform(0.012, 0.020))

        # Hai cánh (V shape đơn giản)
        for dx, flip in [(-size * 0.6, 1), (size * 0.6, -1)]:
            wing = ax.plot(
                [bx + dx, bx + dx + flip * size * 0.50],
                [by, by + size * 0.30],
                '-', color="#37474F",
                lw=ctx.lw(0.010), alpha=0.75, zorder=3
            )[0]
            patches.append(wing)


def _draw_evening_shadows(ax, patches, ctx: CanvasCtx):
    """Bóng dài đổ về phía đông khi chiều tà."""
    shadow_positions = [0.05, 0.12, 0.82, 0.92]
    for nx in shadow_positions:
        sx = ctx.x(nx)
        sy = ctx.ground_top

        shadow = mpatches.Polygon(
            [
                (sx - ctx.r(0.012), sy),
                (sx + ctx.r(0.012), sy),
                (sx + ctx.r(0.012) + ctx.r(0.18), sy - ctx.r(0.04)),
                (sx - ctx.r(0.012) + ctx.r(0.18), sy - ctx.r(0.04)),
            ],
            color="#2E7D32", alpha=0.18, zorder=2
        )
        ax.add_patch(shadow); patches.append(shadow)

def animate_background_park_day(ax, ctx, variant: str, t_sec: float) -> list:
    """
    Dynamic elements công viên:
    - Chim bay + vỗ cánh (sunny)
    - Cánh hoa anh đào rơi (date)
    - Đèn cột pulse (evening)
    - Ao gợn sóng (sunny / date)
    """
    arts = []

    # ── Chim vỗ cánh + trôi ngang (sunny) ────────────────────────────────────
    if variant == "sunny":
        for base_nx, nfy, phase in [(0.30, 0.88, 0.0), (0.45, 0.92, 1.3),
                                     (0.55, 0.90, 2.1), (0.65, 0.86, 0.7)]:
            nx   = (base_nx + t_sec * 0.012 + phase * 0.05) % 1.0
            bx   = ctx.x(nx)
            by   = ctx.zone_y("sky", nfy - 0.68)
            flap = math.sin(t_sec * 4.0 + phase) * 0.35 + 0.15
            size = ctx.r(0.016)
            for dx, flip in [(-size * 0.6, 1), (size * 0.6, -1)]:
                wing = ax.plot(
                    [bx + dx, bx + dx + flip * size * 0.50],
                    [by, by + size * flap],
                    "-", color="#37474F", lw=ctx.lw(0.010), alpha=0.75, zorder=3
                )[0]
                arts.append(wing)

    # ── Cánh hoa anh đào rơi (date) ──────────────────────────────────────────
    if variant == "date":
        for base_nx, _, speed, phase in [(0.15, 0.5, 0.08, 0.0), (0.30, 0.8, 0.06, 1.2),
                                          (0.50, 0.3, 0.09, 2.5), (0.65, 0.7, 0.07, 0.8),
                                          (0.80, 0.45, 0.08, 1.9), (0.42, 0.6, 0.05, 3.1)]:
            fall = (t_sec * speed + phase) % 1.0
            py   = ctx.zone_y("sky", 1.0 - fall * 1.3)
            if py < 0:
                continue
            px = ctx.x(base_nx) + math.sin(t_sec * 1.5 + phase) * ctx.r(0.04)
            petal = plt.Circle((px, py), ctx.r(0.010),
                               color="#F8BBD9", alpha=0.75, zorder=4)
            ax.add_patch(petal)
            arts.append(petal)

    # ── Đèn cột pulse (evening) ───────────────────────────────────────────────
    if variant == "evening":
        pulse_alpha = 0.12 + math.sin(t_sec * 1.8) * 0.05
        glow = plt.Circle(
            (ctx.x(0.82), ctx.ground_top + ctx.zone_h("mid") * 0.65 + ctx.r(0.032) * 0.40),
            ctx.r(0.075), color="#FFF9C4", alpha=pulse_alpha, zorder=4
        )
        ax.add_patch(glow)
        arts.append(glow)

    # ── Ao gợn sóng (sunny / date) ───────────────────────────────────────────
    if variant in ("sunny", "date"):
        pond_cx = ctx.x(0.18)
        pond_cy = ctx.ground_top * 0.50
        pond_rx = ctx.r(0.12)
        for k in range(2):
            phase    = (t_sec * 0.8 + k * 0.5) % 1.0
            ripple_r = pond_rx * (0.3 + phase * 0.7)
            ripple   = mpatches.Ellipse(
                (pond_cx, pond_cy), ripple_r * 2, ripple_r * 2 * 0.38,
                facecolor="none", edgecolor="#B0BEC5",
                linewidth=ctx.lw(0.008), alpha=0.35 * (1.0 - phase), zorder=4
            )
            ax.add_patch(ripple)
            arts.append(ripple)

    return arts