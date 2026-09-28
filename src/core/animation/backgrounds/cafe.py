"""
Background: Cafe (Quán cà phê)
Canvas: scale tự động qua CanvasCtx (9:16 / 16:9 / 1:1)

Phù hợp với chủ đề:
  - Làm việc remote, ngồi cafe cả ngày
  - Hẹn hò, gặp gỡ bạn bè
  - Thư giãn cuối tuần với cà phê
  - Deadline trong quán, áp lực nhẹ nhàng hơn
  - Buổi chiều mưa, ngồi nhìn ra cửa sổ

Variants:
  cozy  — ấm áp, ánh đèn vàng, yên tĩnh, ít khách
  busy  — đông đúc, sáng trưng, năng lượng cao
  rainy — mưa ngoài cửa sổ, đèn mờ, không khí tĩnh lặng
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch

from .canvas import CanvasCtx
from .utils import setup_ax, draw_floor_planks, draw_rain
import math

# ── Palette ───────────────────────────────────────────────────────────────────
WALL_COZY    = "#FFF8F0"
WALL_BUSY    = "#FAFAFA"
WALL_RAINY   = "#ECEFF1"

FLOOR_COZY   = "#A1887F"
FLOOR_BUSY   = "#8D6E63"
FLOOR_RAINY  = "#90A4AE"
FLOOR_DARK   = "#6D4C41"

COUNTER_C    = "#5D4037"
COUNTER_TOP  = "#4E342E"
MACHINE_C    = "#37474F"
MACHINE_ACC  = "#B0BEC5"

SHELF_C      = "#6D4C41"
CUP_COLORS   = ["#E53935", "#1565C0", "#2E7D32", "#F57F17", "#4A148C", "#FFFFFF"]
JAR_C        = "#B2DFDB"

TABLE_WOOD   = "#8D6E63"
TABLE_DARK   = "#6D4C41"
CHAIR_C      = "#5D4037"
CHAIR_SEAT   = "#A1887F"

LAMP_HANG_C  = "#37474F"
LAMP_GLOW_C  = "#FFF9C4"
LAMP_SHADE_COZY  = "#FF8F00"
LAMP_SHADE_BUSY  = "#37474F"
LAMP_SHADE_RAINY = "#546E7A"

WINDOW_FRAME_C   = "#5D4037"
WINDOW_SKY_COZY  = "#FFF3E0"
WINDOW_SKY_BUSY  = "#E3F2FD"
WINDOW_SKY_RAINY = "#607D8B"

PLANT_POT    = "#BF8B60"
PLANT_LEAF   = "#388E3C"
PLANT_DARK   = "#2E7D32"

CHALKBOARD_C = "#1B5E20"
MENU_LINE    = "#A5D6A7"

SKIRTING_C   = "#4E342E"
WAINSCOT_C   = "#EFEBE9"


def build_background_cafe(ax, ctx: CanvasCtx, variant: str = "cozy"):
    """
    Vẽ background quán cà phê.

    Args:
        ax      : matplotlib Axes
        ctx     : CanvasCtx — xác định canvas ratio + helpers
        variant : "cozy" | "busy" | "rainy"
    """
    patches = []
    setup_ax(ax, ctx)
    np.random.seed(42)

    is_cozy  = variant == "cozy"
    is_busy  = variant == "busy"
    is_rainy = variant == "rainy"

    wall_c  = WALL_RAINY if is_rainy else (WALL_BUSY if is_busy else WALL_COZY)
    floor_c = FLOOR_RAINY if is_rainy else (FLOOR_BUSY if is_busy else FLOOR_COZY)

    # ── Tường ─────────────────────────────────────────────────────────────────
    wall = mpatches.Rectangle(
        (0, ctx.ground_top), ctx.W, ctx.H - ctx.ground_top,
        color=wall_c, zorder=0
    )
    ax.add_patch(wall); patches.append(wall)

    # Wainscoting — ốp tường dưới
    wainscot_h = ctx.zone_h("mid") * 0.28
    wainscot = mpatches.Rectangle(
        (0, ctx.ground_top), ctx.W, wainscot_h,
        color=WAINSCOT_C, alpha=0.55, zorder=1
    )
    ax.add_patch(wainscot); patches.append(wainscot)

    wainscot_rail = mpatches.Rectangle(
        (0, ctx.ground_top + wainscot_h),
        ctx.W, ctx.r(0.010),
        color=SHELF_C, zorder=2
    )
    ax.add_patch(wainscot_rail); patches.append(wainscot_rail)

    # Chân tường
    skirting = mpatches.Rectangle(
        (0, ctx.ground_top - ctx.r(0.010)),
        ctx.W, ctx.r(0.010),
        color=SKIRTING_C, alpha=0.60, zorder=2
    )
    ax.add_patch(skirting); patches.append(skirting)

    # ── Sàn ───────────────────────────────────────────────────────────────────
    floor = mpatches.Rectangle(
        (0, 0), ctx.W, ctx.ground_top,
        color=floor_c, zorder=1
    )
    ax.add_patch(floor); patches.append(floor)

    draw_floor_planks(ax, patches, ctx,
                      base_color=floor_c,
                      plank_color=FLOOR_DARK,
                      n_lines=5, zorder=2)

    # ── Cửa sổ ────────────────────────────────────────────────────────────────
    _draw_window(ax, patches, ctx, nx=0.72, variant=variant)

    # ── Quầy bar + máy pha cà phê ─────────────────────────────────────────────
    _draw_counter(ax, patches, ctx, variant=variant)

    # ── Kệ tường + cốc/lọ ────────────────────────────────────────────────────
    _draw_wall_shelf(ax, patches, ctx, variant=variant)

    # ── Bảng menu chalk ───────────────────────────────────────────────────────
    _draw_chalkboard(ax, patches, ctx, nx=0.20, variant=variant)

    # ── Bàn + ghế khách ───────────────────────────────────────────────────────
    _draw_table_set(ax, patches, ctx, variant=variant)

    # ── Đèn thả trần ──────────────────────────────────────────────────────────
    _draw_hanging_lamps(ax, patches, ctx, variant=variant)

    # ── Cây cảnh ──────────────────────────────────────────────────────────────
    _draw_plant(ax, patches, ctx, nx=0.04, variant=variant)

    # ── Overlay theo variant ──────────────────────────────────────────────────
    if is_cozy:
        # Ánh đèn vàng ấm lan toả
        warm = mpatches.Rectangle(
            (0, 0), ctx.W, ctx.H,
            color="#FF8F00", alpha=0.04, zorder=9
        )
        ax.add_patch(warm); patches.append(warm)

    if is_rainy:
        # Mưa ngoài cửa sổ (vẽ sau cửa sổ, trước frame)
        _draw_rain_outside(ax, patches, ctx)
        # Overlay lạnh
        cold = mpatches.Rectangle(
            (0, 0), ctx.W, ctx.H,
            color="#546E7A", alpha=0.06, zorder=9
        )
        ax.add_patch(cold); patches.append(cold)

    return patches


# ── Helpers ───────────────────────────────────────────────────────────────────

def _draw_window(ax, patches, ctx: CanvasCtx, nx: float, variant: str):
    """Cửa sổ lớn nhìn ra ngoài."""
    is_cozy  = variant == "cozy"
    is_busy  = variant == "busy"
    is_rainy = variant == "rainy"

    sky_c = (WINDOW_SKY_RAINY if is_rainy
             else WINDOW_SKY_BUSY if is_busy
             else WINDOW_SKY_COZY)

    ww = ctx.r(0.34)
    wh = ctx.r(0.46)
    cx = ctx.x(nx)
    x  = cx - ww / 2
    y  = ctx.zone_y("mid", 0.38)

    # Ngoài trời qua cửa sổ
    sky = mpatches.Rectangle(
        (x + ctx.r(0.008), y + ctx.r(0.008)),
        ww - ctx.r(0.016), wh - ctx.r(0.016),
        color=sky_c, zorder=3
    )
    ax.add_patch(sky); patches.append(sky)

    # Cảnh ngoài đơn giản
    if is_cozy or is_busy:
        # Vài tán cây mờ
        for tx, tr in [(cx - ctx.r(0.08), ctx.r(0.06)),
                       (cx + ctx.r(0.06), ctx.r(0.05))]:
            tree_top = plt.Circle(
                (tx, y + wh * 0.72), tr,
                color="#A5D6A7", alpha=0.45, zorder=4
            )
            ax.add_patch(tree_top); patches.append(tree_top)

        # Mặt trời nhỏ
        sun_alpha = 0.35 if is_busy else 0.25
        sun = plt.Circle(
            (cx + ctx.r(0.10), y + wh * 0.85),
            ctx.r(0.028),
            color="#FFD54F", alpha=sun_alpha, zorder=4
        )
        ax.add_patch(sun); patches.append(sun)

    # Khung cửa sổ — 4 ô
    frame = FancyBboxPatch(
        (x, y), ww, wh,
        boxstyle="square,pad=0",
        edgecolor=WINDOW_FRAME_C,
        linewidth=ctx.lw(0.028),
        facecolor="none", zorder=6
    )
    ax.add_patch(frame); patches.append(frame)

    # Thanh chia dọc + ngang
    for lx in [cx]:
        vl = ax.plot([lx, lx], [y + ctx.r(0.01), y + wh - ctx.r(0.01)],
                     '-', color=WINDOW_FRAME_C,
                     lw=ctx.lw(0.016), zorder=6)[0]
        patches.append(vl)

    hl = ax.plot([x + ctx.r(0.01), x + ww - ctx.r(0.01)],
                 [y + wh * 0.50, y + wh * 0.50],
                 '-', color=WINDOW_FRAME_C,
                 lw=ctx.lw(0.016), zorder=6)[0]
    patches.append(hl)

    # Bậu cửa sổ
    sill = mpatches.Rectangle(
        (x - ctx.r(0.012), y - ctx.r(0.016)),
        ww + ctx.r(0.024), ctx.r(0.018),
        color=SHELF_C, zorder=6
    )
    ax.add_patch(sill); patches.append(sill)

    # Ly cà phê đặt trên bậu cửa sổ (cozy / rainy)
    if is_cozy or is_rainy:
        _draw_cup_on_sill(ax, patches, ctx,
                          cx=cx - ctx.r(0.04), cy=y - ctx.r(0.016))


def _draw_cup_on_sill(ax, patches, ctx: CanvasCtx,
                      cx: float, cy: float):
    """Ly cà phê nhỏ trên bậu cửa sổ."""
    r = ctx.r(0.018)
    cup = FancyBboxPatch(
        (cx - r, cy - r * 1.4),
        r * 2, r * 1.6,
        boxstyle="round,pad=0.003",
        color="#795548", zorder=7
    )
    ax.add_patch(cup); patches.append(cup)

    # Hơi bốc
    for i, (dx, dy) in enumerate([(-r*0.3, r*0.5), (0, r*0.7), (r*0.3, r*0.5)]):
        steam = ax.plot(
            [cx + dx, cx + dx + ctx.r(0.004) * ((-1)**i)],
            [cy + dy, cy + dy + ctx.r(0.020)],
            '-', color="#B0BEC5",
            lw=ctx.lw(0.008), alpha=0.50, zorder=8
        )[0]
        patches.append(steam)


def _draw_counter(ax, patches, ctx: CanvasCtx, variant: str):
    """Quầy bar + máy pha cà phê + tủ kính."""
    is_busy = variant == "busy"

    cw = ctx.W * 0.42
    ch = ctx.r(0.14)
    cx_left = 0
    cy = ctx.ground_top * 0.55

    # Thân quầy
    counter = FancyBboxPatch(
        (cx_left, cy), cw, ch,
        boxstyle="round,pad=0.005",
        color=COUNTER_C, zorder=4
    )
    ax.add_patch(counter); patches.append(counter)

    # Mặt quầy
    top = mpatches.Rectangle(
        (cx_left - ctx.r(0.008), cy + ch),
        cw + ctx.r(0.016), ctx.r(0.012),
        color=COUNTER_TOP, zorder=5
    )
    ax.add_patch(top); patches.append(top)

    # Máy pha cà phê
    _draw_espresso_machine(ax, patches, ctx,
                           cx=ctx.x(0.22), cy=cy + ch,
                           variant=variant)

    # Máy xay (busy thêm 1 máy)
    if is_busy:
        _draw_grinder(ax, patches, ctx,
                      cx=ctx.x(0.10), cy=cy + ch)

    # Tủ kính bánh nhỏ (bên phải quầy)
    _draw_display_case(ax, patches, ctx,
                       cx_left=cw + ctx.r(0.010), cy=cy, ch=ch)


def _draw_espresso_machine(ax, patches, ctx: CanvasCtx,
                            cx: float, cy: float, variant: str):
    """Máy pha espresso."""
    mw = ctx.r(0.12)
    mh = ctx.r(0.11)

    body = FancyBboxPatch(
        (cx - mw / 2, cy), mw, mh,
        boxstyle="round,pad=0.006",
        color=MACHINE_C, zorder=6
    )
    ax.add_patch(body); patches.append(body)

    # Mặt máy sáng
    face = FancyBboxPatch(
        (cx - mw * 0.35, cy + mh * 0.20),
        mw * 0.70, mh * 0.45,
        boxstyle="round,pad=0.004",
        color=MACHINE_ACC, alpha=0.30, zorder=7
    )
    ax.add_patch(face); patches.append(face)

    # Vòi steam 2 bên
    for side in [-1, 1]:
        wand = ax.plot(
            [cx + side * mw * 0.44, cx + side * mw * 0.52],
            [cy + mh * 0.18, cy + mh * 0.05],
            '-', color=MACHINE_ACC,
            lw=ctx.lw(0.018), zorder=7
        )[0]
        patches.append(wand)

    # Đèn báo
    led = plt.Circle(
        (cx, cy + mh * 0.82), ctx.r(0.008),
        color="#4CAF50" if variant != "rainy" else "#FF5722",
        zorder=8
    )
    ax.add_patch(led); patches.append(led)

    # Khay hứng
    tray = mpatches.Rectangle(
        (cx - mw * 0.40, cy - ctx.r(0.014)),
        mw * 0.80, ctx.r(0.016),
        color=MACHINE_ACC, alpha=0.60, zorder=7
    )
    ax.add_patch(tray); patches.append(tray)


def _draw_grinder(ax, patches, ctx: CanvasCtx,
                  cx: float, cy: float):
    """Máy xay cà phê (busy variant)."""
    gw = ctx.r(0.065)
    gh = ctx.r(0.090)

    body = FancyBboxPatch(
        (cx - gw / 2, cy), gw, gh,
        boxstyle="round,pad=0.005",
        color="#455A64", zorder=6
    )
    ax.add_patch(body); patches.append(body)

    # Hộp đựng hạt (trên)
    hopper = FancyBboxPatch(
        (cx - gw * 0.35, cy + gh),
        gw * 0.70, gh * 0.42,
        boxstyle="round,pad=0.004",
        color="#607D8B", zorder=6
    )
    ax.add_patch(hopper); patches.append(hopper)


def _draw_display_case(ax, patches, ctx: CanvasCtx,
                        cx_left: float, cy: float, ch: float):
    """Tủ kính trưng bày bánh."""
    dw = ctx.r(0.16)
    dh = ch * 1.15

    # Khung tủ
    case = FancyBboxPatch(
        (cx_left, cy), dw, dh,
        boxstyle="round,pad=0.004",
        color=COUNTER_C, alpha=0.80, zorder=4
    )
    ax.add_patch(case); patches.append(case)

    # Kính
    glass = FancyBboxPatch(
        (cx_left + ctx.r(0.008), cy + ctx.r(0.010)),
        dw - ctx.r(0.016), dh - ctx.r(0.020),
        boxstyle="round,pad=0.003",
        color="#E3F2FD", alpha=0.30, zorder=5
    )
    ax.add_patch(glass); patches.append(glass)

    # Bánh đơn giản (hình chữ nhật màu)
    cake_colors = ["#F48FB1", "#FFCC80", "#A5D6A7"]
    for i, cc in enumerate(cake_colors):
        cake = FancyBboxPatch(
            (cx_left + ctx.r(0.012), cy + dh * (0.12 + i * 0.28)),
            dw - ctx.r(0.024), dh * 0.18,
            boxstyle="round,pad=0.003",
            color=cc, alpha=0.80, zorder=6
        )
        ax.add_patch(cake); patches.append(cake)


def _draw_wall_shelf(ax, patches, ctx: CanvasCtx, variant: str):
    """Kệ tường phía sau quầy + cốc + lọ."""
    is_cozy = variant == "cozy"
    shelf_y_base = ctx.zone_y("mid", 0.55)
    shelf_w = ctx.W * 0.44

    for fi in range(2):
        sy = shelf_y_base + fi * ctx.r(0.12)

        plank = mpatches.Rectangle(
            (0, sy), shelf_w, ctx.r(0.010),
            color=SHELF_C, zorder=5
        )
        ax.add_patch(plank); patches.append(plank)

        # Đồ trên kệ
        np.random.seed(fi * 10 + 20)
        item_x = ctx.r(0.014)
        while item_x < shelf_w - ctx.r(0.020):
            # Xen kẽ cốc và lọ
            if np.random.random() > 0.38:
                # Cốc
                iw = ctx.r(np.random.uniform(0.020, 0.030))
                ih = ctx.r(np.random.uniform(0.032, 0.048))
                ic = CUP_COLORS[np.random.randint(len(CUP_COLORS))]
                item = FancyBboxPatch(
                    (item_x, sy + ctx.r(0.010)), iw, ih,
                    boxstyle="round,pad=0.003",
                    color=ic, alpha=0.88, zorder=6
                )
            else:
                # Lọ thủy tinh
                iw = ctx.r(np.random.uniform(0.022, 0.032))
                ih = ctx.r(np.random.uniform(0.040, 0.060))
                item = FancyBboxPatch(
                    (item_x, sy + ctx.r(0.010)), iw, ih,
                    boxstyle="round,pad=0.004",
                    color=JAR_C, alpha=0.50, zorder=6
                )
            ax.add_patch(item); patches.append(item)
            item_x += iw + ctx.r(0.008)


def _draw_chalkboard(ax, patches, ctx: CanvasCtx,
                     nx: float, variant: str):
    """Bảng menu viết phấn."""
    cx = ctx.x(nx)
    bw = ctx.r(0.26)
    bh = ctx.r(0.32)
    y  = ctx.zone_y("mid", 0.42)
    x  = cx - bw / 2

    # Khung
    frame = FancyBboxPatch(
        (x - ctx.r(0.010), y - ctx.r(0.010)),
        bw + ctx.r(0.020), bh + ctx.r(0.020),
        boxstyle="round,pad=0.005",
        color=SHELF_C, zorder=4
    )
    ax.add_patch(frame); patches.append(frame)

    # Nền bảng
    board = mpatches.Rectangle(
        (x, y), bw, bh,
        color=CHALKBOARD_C, zorder=5
    )
    ax.add_patch(board); patches.append(board)

    # Chữ "MENU" giả (sọc phấn)
    title_y = y + bh * 0.82
    title_w = bw * 0.55
    title = mpatches.Rectangle(
        (x + (bw - title_w) / 2, title_y),
        title_w, ctx.r(0.012),
        color="#FFFFFF", alpha=0.75, zorder=6
    )
    ax.add_patch(title); patches.append(title)

    # Đường kẻ menu items
    for i in range(4):
        line_y = y + bh * (0.62 - i * 0.155)
        lw_frac = np.random.uniform(0.45, 0.72)
        menu_line = mpatches.Rectangle(
            (x + bw * 0.10, line_y),
            bw * lw_frac, ctx.r(0.007),
            color=MENU_LINE, alpha=0.55, zorder=6
        )
        ax.add_patch(menu_line); patches.append(menu_line)

        # Giá (ngắn hơn, bên phải)
        price = mpatches.Rectangle(
            (x + bw * 0.75, line_y),
            bw * 0.18, ctx.r(0.007),
            color=MENU_LINE, alpha=0.45, zorder=6
        )
        ax.add_patch(price); patches.append(price)

    # Phấn + máng phấn
    tray = mpatches.Rectangle(
        (x, y - ctx.r(0.016)), bw, ctx.r(0.014),
        color=SHELF_C, zorder=5
    )
    ax.add_patch(tray); patches.append(tray)

    for i, cc in enumerate(["#FFFFFF", "#FFCCBC", "#B3E5FC"]):
        chalk = mpatches.Rectangle(
            (x + bw * (0.15 + i * 0.12), y - ctx.r(0.013)),
            bw * 0.07, ctx.r(0.009),
            color=cc, alpha=0.90, zorder=6
        )
        ax.add_patch(chalk); patches.append(chalk)


def _draw_table_set(ax, patches, ctx: CanvasCtx, variant: str):
    """Bàn tròn + ghế khách."""
    is_busy = variant == "busy"

    # 1 bàn chính giữa (foreground)
    # busy thêm 1 bàn nhỏ bên phải
    tables = [(0.50, 0.58)]
    if is_busy:
        tables.append((0.80, 0.38))

    for nx, scale in tables:
        _draw_one_table(ax, patches, ctx, nx=nx, scale=scale, variant=variant)


def _draw_one_table(ax, patches, ctx: CanvasCtx,
                    nx: float, scale: float, variant: str):
    """1 bàn tròn + 2 ghế."""
    cx  = ctx.x(nx)
    ty  = ctx.ground_top * 0.62
    tr  = ctx.r(0.095) * scale   # table radius

    # Mặt bàn
    table = plt.Circle(
        (cx, ty), tr,
        facecolor=TABLE_WOOD,
        edgecolor=TABLE_DARK,
        linewidth=ctx.lw(0.014),
        zorder=4
    )
    ax.add_patch(table); patches.append(table)

    # Chân bàn
    leg = ax.plot(
        [cx, cx],
        [ty - tr, ty - tr - ctx.r(0.045) * scale],
        '-', color=TABLE_DARK,
        lw=ctx.lw(0.022), zorder=4
    )[0]
    patches.append(leg)

    # Đế chân bàn (chữ T)
    base = mpatches.Rectangle(
        (cx - ctx.r(0.042) * scale, ty - tr - ctx.r(0.050) * scale),
        ctx.r(0.084) * scale, ctx.r(0.008),
        color=TABLE_DARK, zorder=4
    )
    ax.add_patch(base); patches.append(base)

    # Ly + đồ trên bàn
    _draw_table_items(ax, patches, ctx, cx=cx, ty=ty, variant=variant)

    # Ghế 2 bên (đơn giản — chỉ vẽ phần trên, phần dưới bị bàn che)
    for side in [-1, 1]:
        chair_cx = cx + side * (tr + ctx.r(0.040) * scale)
        _draw_chair(ax, patches, ctx, cx=chair_cx, ty=ty, scale=scale)


def _draw_chair(ax, patches, ctx: CanvasCtx,
                cx: float, ty: float, scale: float):
    """Ghế cafe đơn giản."""
    sw = ctx.r(0.065) * scale
    sh = ctx.r(0.025) * scale

    # Mặt ghế
    seat = FancyBboxPatch(
        (cx - sw / 2, ty - sh / 2),
        sw, sh,
        boxstyle="round,pad=0.004",
        color=CHAIR_SEAT, zorder=3
    )
    ax.add_patch(seat); patches.append(seat)

    # Lưng ghế
    back_h = ctx.r(0.055) * scale
    back = FancyBboxPatch(
        (cx - sw * 0.40, ty + sh / 2),
        sw * 0.80, back_h,
        boxstyle="round,pad=0.004",
        color=CHAIR_C, zorder=3
    )
    ax.add_patch(back); patches.append(back)

    # Chân ghế (2 cái nhìn thấy)
    for lx in [cx - sw * 0.28, cx + sw * 0.28]:
        leg = ax.plot(
            [lx, lx],
            [ty - sh / 2, ty - sh / 2 - ctx.r(0.030) * scale],
            '-', color=CHAIR_C,
            lw=ctx.lw(0.014), zorder=3
        )[0]
        patches.append(leg)


def _draw_table_items(ax, patches, ctx: CanvasCtx,
                      cx: float, ty: float, variant: str):
    """Ly + đồ nhỏ trên mặt bàn."""
    is_rainy = variant == "rainy"

    # Ly cà phê
    r = ctx.r(0.014)
    cup = FancyBboxPatch(
        (cx - r * 0.8, ty - r * 1.2),
        r * 1.6, r * 1.4,
        boxstyle="round,pad=0.003",
        color="#795548", zorder=6
    )
    ax.add_patch(cup); patches.append(cup)

    # Đĩa lót
    saucer = mpatches.Ellipse(
        (cx, ty - r * 1.28), r * 2.4, r * 0.55,
        color="#BDBDBD", zorder=5
    )
    ax.add_patch(saucer); patches.append(saucer)

    # Laptop (busy / rainy)
    if variant in ("busy", "rainy"):
        lw_ = ctx.r(0.075)
        lh_ = ctx.r(0.045)
        laptop = FancyBboxPatch(
            (cx + r * 1.5, ty - lh_ / 2),
            lw_, lh_,
            boxstyle="round,pad=0.004",
            color="#37474F", zorder=6
        )
        ax.add_patch(laptop); patches.append(laptop)

        screen = FancyBboxPatch(
            (cx + r * 1.5 + ctx.r(0.006), ty - lh_ / 2 + ctx.r(0.006)),
            lw_ - ctx.r(0.012), lh_ - ctx.r(0.012),
            boxstyle="round,pad=0.003",
            color="#B3E5FC", alpha=0.50, zorder=7
        )
        ax.add_patch(screen); patches.append(screen)


def _draw_hanging_lamps(ax, patches, ctx: CanvasCtx, variant: str):
    """Đèn thả trần — nét đặc trưng quán cafe."""
    is_cozy  = variant == "cozy"
    is_rainy = variant == "rainy"

    shade_c = (LAMP_SHADE_COZY  if is_cozy
               else LAMP_SHADE_RAINY if is_rainy
               else LAMP_SHADE_BUSY)

    lamp_positions = [ctx.x(0.28), ctx.x(0.55), ctx.x(0.80)]
    ceiling_y = ctx.H - ctx.r(0.015)

    for lx in lamp_positions:
        cord_len = ctx.zone_h("mid") * (0.28 if is_cozy else 0.22)
        lamp_y   = ceiling_y - cord_len

        # Dây điện
        cord = ax.plot(
            [lx, lx],
            [ceiling_y, lamp_y + ctx.r(0.028)],
            '-', color=LAMP_HANG_C,
            lw=ctx.lw(0.010), zorder=7
        )[0]
        patches.append(cord)

        # Chụp đèn
        shade_w = ctx.r(0.055)
        shade_h = ctx.r(0.040)
        shade = FancyBboxPatch(
            (lx - shade_w / 2, lamp_y),
            shade_w, shade_h,
            boxstyle="round,pad=0.005",
            color=shade_c, zorder=8
        )
        ax.add_patch(shade); patches.append(shade)

        # Bóng đèn
        bulb = plt.Circle(
            (lx, lamp_y + shade_h * 0.35),
            ctx.r(0.012),
            color=LAMP_GLOW_C, alpha=0.95, zorder=9
        )
        ax.add_patch(bulb); patches.append(bulb)

        # Glow
        glow_alpha = 0.20 if is_cozy else (0.14 if is_rainy else 0.08)
        glow_r = ctx.r(0.075) if is_cozy else ctx.r(0.055)
        glow = plt.Circle(
            (lx, lamp_y + shade_h * 0.35),
            glow_r,
            color=LAMP_GLOW_C, alpha=glow_alpha, zorder=6
        )
        ax.add_patch(glow); patches.append(glow)

        # Cone ánh sáng xuống (cozy / rainy)
        if is_cozy or is_rainy:
            cone_alpha = 0.06 if is_cozy else 0.04
            cone = mpatches.Polygon(
                [
                    (lx - shade_w * 0.50, lamp_y),
                    (lx + shade_w * 0.50, lamp_y),
                    (lx + ctx.r(0.10),    lamp_y - ctx.r(0.18)),
                    (lx - ctx.r(0.10),    lamp_y - ctx.r(0.18)),
                ],
                color=LAMP_GLOW_C, alpha=cone_alpha, zorder=6
            )
            ax.add_patch(cone); patches.append(cone)


def _draw_plant(ax, patches, ctx: CanvasCtx, nx: float, variant: str):
    """Cây cảnh góc quán."""
    cx = ctx.x(nx)
    pot_y = ctx.ground_top

    pot_w = ctx.r(0.055)
    pot_h = ctx.r(0.065)

    # Chậu
    pot = FancyBboxPatch(
        (cx - pot_w / 2, pot_y),
        pot_w, pot_h,
        boxstyle="round,pad=0.004",
        color=PLANT_POT, zorder=5
    )
    ax.add_patch(pot); patches.append(pot)

    # Đất trong chậu
    soil = mpatches.Ellipse(
        (cx, pot_y + pot_h), pot_w * 0.90, ctx.r(0.016),
        color="#4E342E", zorder=6
    )
    ax.add_patch(soil); patches.append(soil)

    # Thân cây nhỏ
    stem_h = ctx.r(0.10)
    stem = ax.plot(
        [cx, cx],
        [pot_y + pot_h, pot_y + pot_h + stem_h],
        '-', color=PLANT_DARK,
        lw=ctx.lw(0.018), zorder=6
    )[0]
    patches.append(stem)

    # Lá — nhiều tán
    leaf_top = pot_y + pot_h + stem_h
    leaf_c = PLANT_DARK if variant == "rainy" else PLANT_LEAF
    for lx, ly, lr in [
        (cx,           leaf_top + ctx.r(0.055), ctx.r(0.055)),
        (cx - ctx.r(0.040), leaf_top + ctx.r(0.022), ctx.r(0.038)),
        (cx + ctx.r(0.038), leaf_top + ctx.r(0.018), ctx.r(0.034)),
        (cx - ctx.r(0.022), leaf_top + ctx.r(0.082), ctx.r(0.032)),
        (cx + ctx.r(0.020), leaf_top + ctx.r(0.078), ctx.r(0.030)),
    ]:
        lf = plt.Circle((lx, ly), lr,
                         color=leaf_c, alpha=0.90, zorder=7)
        ax.add_patch(lf); patches.append(lf)


def _draw_rain_outside(ax, patches, ctx: CanvasCtx):
    """Mưa chỉ vẽ trong vùng cửa sổ (rainy variant)."""
    nx  = 0.72
    ww  = ctx.r(0.34)
    wh  = ctx.r(0.46)
    cx  = ctx.x(nx)
    x   = cx - ww / 2
    y   = ctx.zone_y("mid", 0.38)

    np.random.seed(88)
    rng = np.random
    for _ in range(28):
        rx = rng.uniform(x + ctx.r(0.01), x + ww - ctx.r(0.01))
        ry = rng.uniform(y + ctx.r(0.02), y + wh - ctx.r(0.02))
        rl = ctx.r(rng.uniform(0.018, 0.032))

        rain = ax.plot(
            [rx, rx - rl * 0.15],
            [ry, ry - rl],
            '-', color="#90CAF9",
            lw=ctx.lw(0.008),
            alpha=rng.uniform(0.25, 0.50),
            zorder=5
        )[0]
        patches.append(rain)



def animate_background_cafe(ax, ctx, variant: str, t_sec: float) -> list:
    """
    Dynamic elements cafe:
    - Đèn thả glow pulse (cozy / rainy)
    - Hơi bốc từ ly cửa sổ (cozy / rainy)
    - Mưa ngoài cửa sổ động (rainy)
    """
    arts = []

    # ── Đèn thả glow pulse ────────────────────────────────────────────────────
    if variant in ("cozy", "rainy"):
        ceiling_y = ctx.H - ctx.r(0.015)
        cord_len  = ctx.zone_h("mid") * (0.28 if variant == "cozy" else 0.22)
        shade_h   = ctx.r(0.040)
        lamp_y    = ceiling_y - cord_len
        glow_r    = ctx.r(0.075) if variant == "cozy" else ctx.r(0.055)
        for i, lx in enumerate([ctx.x(0.28), ctx.x(0.55), ctx.x(0.80)]):
            pulse = (0.18 if variant == "cozy" else 0.12) + math.sin(t_sec * 1.5 + i * 0.8) * 0.04
            glow  = plt.Circle((lx, lamp_y + shade_h * 0.35), glow_r,
                               color="#FFF9C4", alpha=pulse, zorder=6)
            ax.add_patch(glow)
            arts.append(glow)

    # ── Hơi bốc từ ly cửa sổ (cozy / rainy) ─────────────────────────────────
    if variant in ("cozy", "rainy"):
        cup_cx = ctx.x(0.72) - ctx.r(0.04)
        cup_cy = ctx.zone_y("mid", 0.38) - ctx.r(0.016)
        r      = ctx.r(0.018)
        for i, (dx, dy) in enumerate([(-r*0.3, r*0.5), (0, r*0.7), (r*0.3, r*0.5)]):
            sx    = cup_cx + dx + math.sin(t_sec * 2.0 + i) * ctx.r(0.006)
            steam = ax.plot(
                [sx, sx + ctx.r(0.004) * math.sin(t_sec + i)],
                [cup_cy + dy, cup_cy + dy + ctx.r(0.022)],
                "-", color="#B0BEC5", lw=ctx.lw(0.008), alpha=0.45, zorder=8
            )[0]
            arts.append(steam)

    # ── Mưa ngoài cửa sổ động (rainy) ────────────────────────────────────────
    if variant == "rainy":
        ww  = ctx.r(0.34)
        wh  = ctx.r(0.46)
        cx  = ctx.x(0.72)
        x   = cx - ww / 2
        y   = ctx.zone_y("mid", 0.38)
        rng = np.random.RandomState(int(t_sec * 12) % 200 + 88)
        for _ in range(10):
            rx      = rng.uniform(x + ctx.r(0.01), x + ww - ctx.r(0.01))
            ry_base = rng.uniform(y + ctx.r(0.02), y + wh - ctx.r(0.02))
            ry      = y + ((ry_base - y + t_sec * ctx.r(0.15)) % (wh - ctx.r(0.04))) + ctx.r(0.02)
            rl      = ctx.r(rng.uniform(0.018, 0.032))
            rain    = ax.plot([rx, rx - rl * 0.15], [ry, ry - rl],
                              "-", color="#90CAF9", lw=ctx.lw(0.008),
                              alpha=rng.uniform(0.25, 0.50), zorder=5)[0]
            arts.append(rain)

    return arts