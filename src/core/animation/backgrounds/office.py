"""
Background: Office (Văn phòng)
Canvas: scale tự động qua CanvasCtx (9:16 / 16:9 / 1:1)

Phù hợp với chủ đề:
  - Deadline, overtime, áp lực công việc
  - Sếp toxic, đồng nghiệp drama
  - Burnout, rat race, 9-5 grind
  - Monday mood, cuối tháng lương

Variants:
  day      — văn phòng ban ngày bình thường
  night    — đêm khuya, chỉ có đèn màn hình
  deadline — đống giấy tờ, ly cà phê, chaos
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Arc
import math

from .canvas import CanvasCtx
from .utils import setup_ax, draw_floor_planks

# ── Palette ───────────────────────────────────────────────────────────────────
WALL_DAY    = "#F0EDE8"
WALL_NIGHT  = "#1A1A2E"
FLOOR_COLOR = "#C8B89A"
FLOOR_DARK  = "#B5A48A"
DESK_COLOR  = "#8B6F47"
DESK_LEG    = "#6B5237"
MONITOR_BODY   = "#1A1A2E"
MONITOR_SCREEN = "#0D1B2A"
MONITOR_GLOW   = "#4FC3F7"
WINDOW_FRAME   = "#8B6F47"
PLANT_POT      = "#A0522D"
PLANT_LEAF     = "#2E7D32"
SHELF_COLOR    = "#9E7B5A"
BOOK_COLORS    = ["#E53935", "#1565C0", "#2E7D32", "#F57F17", "#6A1B9A"]
LAMP_BASE      = "#455A64"
LAMP_GLOW      = "#FFF9C4"
SIGN_COLORS    = ["#FFE082", "#80CBC4", "#EF9A9A"]


def build_background_office(ax, ctx: CanvasCtx, variant: str = "day"):
    """
    Vẽ background văn phòng. Tọa độ tự scale theo ctx.

    Args:
        ax      : matplotlib Axes
        ctx     : CanvasCtx — xác định canvas ratio + helpers
        variant : "day" | "night" | "deadline"
    """
    patches = []
    setup_ax(ax, ctx)
    np.random.seed(42)

    is_night    = variant == "night"
    is_deadline = variant == "deadline"

    wall_c  = WALL_NIGHT  if is_night else WALL_DAY
    floor_c = "#12100E"   if is_night else FLOOR_COLOR
    sky_c   = "#05050F"   if is_night else ("#FFF3E0" if is_deadline else "#87CEEB")

    # ── Tường ────────────────────────────────────────────────────────────────
    wall = mpatches.Rectangle(
        (0, ctx.ground_top), ctx.W, ctx.H - ctx.ground_top,
        color=wall_c, zorder=0
    )
    ax.add_patch(wall); patches.append(wall)

    # ── Sàn ──────────────────────────────────────────────────────────────────
    floor = mpatches.Rectangle(
        (0, 0), ctx.W, ctx.ground_top,
        color=floor_c, zorder=1
    )
    ax.add_patch(floor); patches.append(floor)

    if not is_night:
        draw_floor_planks(ax, patches, ctx,
                          base_color=floor_c, plank_color=FLOOR_DARK,
                          n_lines=5, zorder=2)

    # Chân tường
    skirting = mpatches.Rectangle(
        (0, ctx.ground_top - ctx.r(0.012)),
        ctx.W, ctx.r(0.012),
        color=DESK_LEG, alpha=0.45, zorder=2
    )
    ax.add_patch(skirting); patches.append(skirting)

    # ── Cửa sổ ───────────────────────────────────────────────────────────────
    _draw_window(ax, patches, ctx,
                 nx=0.25, sky_c=sky_c, variant=variant)
    _draw_window(ax, patches, ctx,
                 nx=0.75, sky_c=sky_c, variant=variant)

    # ── Kệ sách (bên trái) ───────────────────────────────────────────────────
    _draw_bookshelf(ax, patches, ctx, nx=0.02, variant=variant)

    # ── Bảng trắng (bên phải) ────────────────────────────────────────────────
    _draw_whiteboard(ax, patches, ctx, nx=0.76, variant=variant)

    # ── Bàn làm việc ─────────────────────────────────────────────────────────
    _draw_desk(ax, patches, ctx, variant=variant)

    # ── Đồng hồ tường ────────────────────────────────────────────────────────
    _draw_wall_clock(ax, patches, ctx, nx=0.50, ny=0.80)

    # ── Cây xanh góc phải ────────────────────────────────────────────────────
    _draw_plant(ax, patches, ctx, nx=0.90, variant=variant)

    # ── Overlay tối (đêm) ────────────────────────────────────────────────────
    if is_night:
        dark = mpatches.Rectangle(
            (0, 0), ctx.W, ctx.H,
            color="#050408", alpha=0.40, zorder=8
        )
        ax.add_patch(dark); patches.append(dark)

    return patches


# ── Helpers ───────────────────────────────────────────────────────────────────

def _draw_window(ax, patches, ctx: CanvasCtx, nx: float,
                 sky_c: str, variant: str):
    """Cửa sổ văn phòng nhìn ra ngoài trời."""
    is_night = variant == "night"

    # Kích thước cửa sổ — normalized
    ww = ctx.r(0.28)   # width
    wh = ctx.r(0.36)   # height
    cx = ctx.x(nx)
    # y đặt ở 65%→90% của mid zone
    cy_bot = ctx.zone_y("mid", 0.62)
    cy_top = cy_bot + wh

    x = cx - ww / 2

    # Nền trời trong cửa sổ
    sky = mpatches.Rectangle(
        (x + ctx.r(0.008), cy_bot + ctx.r(0.008)),
        ww - ctx.r(0.016), wh - ctx.r(0.016),
        color=sky_c, zorder=3
    )
    ax.add_patch(sky); patches.append(sky)

    if is_night:
        # Sao + trăng
        np.random.seed(7)
        for _ in range(12):
            sx = np.random.uniform(x + ctx.r(0.02), x + ww - ctx.r(0.02))
            sy = np.random.uniform(cy_bot + ctx.r(0.04), cy_top - ctx.r(0.02))
            st = ax.plot([sx], [sy], '*', color="#FFF9C4",
                         markersize=ctx.r(0.018) * 10,
                         alpha=np.random.uniform(0.4, 0.9), zorder=4)[0]
            patches.append(st)
        moon = plt.Circle(
            (cx + ctx.r(0.06), cy_top - ctx.r(0.08)),
            ctx.r(0.042),
            color="#FFF9C4", alpha=0.9, zorder=4
        )
        ax.add_patch(moon); patches.append(moon)
    else:
        # Tòa nhà xa + mây nhỏ
        for i, (bnx, bnh_frac, bc) in enumerate([
            (nx - 0.08, 0.40, "#90A4AE"),
            (nx - 0.02, 0.55, "#78909C"),
            (nx + 0.05, 0.32, "#B0BEC5"),
        ]):
            bx  = ctx.x(bnx) - ctx.r(0.022)
            bh_ = wh * bnh_frac
            if bx > x + ctx.r(0.01) and bx + ctx.r(0.044) < x + ww - ctx.r(0.01):
                b = mpatches.Rectangle(
                    (bx, cy_bot + ctx.r(0.01)),
                    ctx.r(0.044), bh_,
                    color=bc, alpha=0.55, zorder=4
                )
                ax.add_patch(b); patches.append(b)

    # Khung cửa sổ
    frame = mpatches.FancyBboxPatch(
        (x, cy_bot), ww, wh,
        boxstyle="square,pad=0",
        edgecolor=WINDOW_FRAME,
        linewidth=ctx.lw(0.025),
        facecolor="none", zorder=6
    )
    ax.add_patch(frame); patches.append(frame)

    # Thanh chia dọc + ngang
    mid_x = ax.plot([cx, cx],
                    [cy_bot + ctx.r(0.01), cy_top - ctx.r(0.01)],
                    '-', color=WINDOW_FRAME,
                    lw=ctx.lw(0.018), zorder=6)[0]
    patches.append(mid_x)

    mid_y_val = cy_bot + wh / 2
    mid_y = ax.plot([x + ctx.r(0.01), x + ww - ctx.r(0.01)],
                    [mid_y_val, mid_y_val],
                    '-', color=WINDOW_FRAME,
                    lw=ctx.lw(0.014), zorder=6)[0]
    patches.append(mid_y)


def _draw_bookshelf(ax, patches, ctx: CanvasCtx, nx: float, variant: str):
    """Kệ sách gắn tường bên trái."""
    is_night = variant == "night"
    shelf_c  = "#4E342E" if is_night else SHELF_COLOR

    sw = ctx.r(0.26)   # shelf width
    sh = ctx.r(0.30)   # shelf height
    x  = ctx.x(nx)
    y  = ctx.zone_y("mid", 0.35)

    # Thân kệ
    back = mpatches.Rectangle(
        (x, y), sw, sh,
        color=shelf_c, alpha=0.28, zorder=3
    )
    ax.add_patch(back); patches.append(back)

    # 3 tầng kệ
    plank_h = ctx.r(0.012)
    for fi in range(3):
        py = y + sh * fi / 3
        plank = mpatches.Rectangle(
            (x, py), sw, plank_h,
            color=shelf_c, zorder=4
        )
        ax.add_patch(plank); patches.append(plank)

    # Sách
    np.random.seed(42)
    for fi in range(2):
        bx = x + ctx.r(0.008)
        shelf_y = y + sh * fi / 3 + plank_h + ctx.r(0.004)
        while bx < x + sw - ctx.r(0.015):
            bw_ = ctx.r(np.random.uniform(0.014, 0.024))
            bh_ = ctx.r(np.random.uniform(0.032, 0.050))
            bc  = "#2C3E50" if is_night else BOOK_COLORS[np.random.randint(len(BOOK_COLORS))]
            book = mpatches.Rectangle(
                (bx, shelf_y), bw_, bh_,
                color=bc, zorder=5
            )
            ax.add_patch(book); patches.append(book)
            bx += bw_ + ctx.r(0.003)


def _draw_whiteboard(ax, patches, ctx: CanvasCtx, nx: float, variant: str):
    """Bảng trắng với sticky notes."""
    is_night = variant == "night"
    board_c  = "#263238" if is_night else "#ECEFF1"

    bw = ctx.r(0.38)
    bh = ctx.r(0.32)
    cx = ctx.x(nx)
    y  = ctx.zone_y("mid", 0.38)
    x  = cx - bw / 2

    # Khung
    frame = mpatches.FancyBboxPatch(
        (x - ctx.r(0.01), y - ctx.r(0.01)),
        bw + ctx.r(0.02), bh + ctx.r(0.02),
        boxstyle="round,pad=0.01",
        color=DESK_LEG, zorder=3
    )
    ax.add_patch(frame); patches.append(frame)

    # Mặt bảng
    board = mpatches.Rectangle(
        (x, y), bw, bh, color=board_c, zorder=4
    )
    ax.add_patch(board); patches.append(board)

    # Đường kẻ
    line_c = "#546E7A" if is_night else "#B0BEC5"
    for i in range(3):
        ly = y + bh * (i + 1) / 4
        lw_ = ctx.r(np.random.uniform(0.08, 0.22))
        ln = ax.plot([x + ctx.r(0.02), x + ctx.r(0.02) + lw_],
                     [ly, ly], '-', color=line_c,
                     lw=ctx.lw(0.010), alpha=0.6, zorder=5)[0]
        patches.append(ln)

    # Sticky notes
    note_colors = SIGN_COLORS
    for i, (nfx, bc) in enumerate([(0.15, note_colors[0]),
                                    (0.45, note_colors[1]),
                                    (0.72, note_colors[2])]):
        note = mpatches.FancyBboxPatch(
            (x + bw * nfx, y + bh * 0.50),
            ctx.r(0.060), ctx.r(0.055),
            boxstyle="round,pad=0.003",
            color=bc, alpha=0.88, zorder=5
        )
        ax.add_patch(note); patches.append(note)

    # Rail trên
    rail = mpatches.Rectangle(
        (x, y + bh - ctx.r(0.010)),
        bw, ctx.r(0.012),
        color=DESK_LEG, zorder=5
    )
    ax.add_patch(rail); patches.append(rail)


def _draw_desk(ax, patches, ctx: CanvasCtx, variant: str):
    """Bàn làm việc + màn hình + đồ vật."""
    is_night    = variant == "night"
    is_deadline = variant == "deadline"
    desk_c = "#4E2A04" if is_night else DESK_COLOR

    # Mặt bàn — đặt ở đáy mid zone
    desk_y = ctx.zone_y("mid", 0.05)
    desk_h = ctx.r(0.032)
    desk_w = ctx.W * 0.88

    desk_top = mpatches.FancyBboxPatch(
        (ctx.W * 0.06, desk_y), desk_w, desk_h,
        boxstyle="round,pad=0.004",
        color=desk_c, zorder=5
    )
    ax.add_patch(desk_top); patches.append(desk_top)

    # Chân bàn
    for lnx in [0.10, 0.90]:
        leg = mpatches.Rectangle(
            (ctx.x(lnx) - ctx.r(0.016), ctx.ground_top),
            ctx.r(0.032), desk_y - ctx.ground_top,
            color=DESK_LEG, zorder=4
        )
        ax.add_patch(leg); patches.append(leg)

    # Màn hình
    _draw_monitor(ax, patches, ctx,
                  nx=0.50, y_base=desk_y + desk_h,
                  variant=variant)

    # Ly cà phê
    _draw_coffee_cup(ax, patches, ctx,
                     nx=0.78, y_base=desk_y + desk_h,
                     variant=variant)

    # Giấy tờ
    _draw_papers(ax, patches, ctx,
                 nx=0.18, y_base=desk_y + desk_h,
                 variant=variant)

    # Bàn phím
    kb = mpatches.FancyBboxPatch(
        (ctx.x(0.36), desk_y + desk_h + ctx.r(0.004)),
        ctx.r(0.22), ctx.r(0.025),
        boxstyle="round,pad=0.003",
        color="#37474F", alpha=0.82, zorder=6
    )
    ax.add_patch(kb); patches.append(kb)

    # Đèn bàn
    _draw_desk_lamp(ax, patches, ctx,
                    nx=0.08, y_base=desk_y + desk_h,
                    variant=variant)


def _draw_monitor(ax, patches, ctx: CanvasCtx,
                  nx: float, y_base: float, variant: str):
    """Màn hình máy tính."""
    is_night = variant == "night"
    cx = ctx.x(nx)
    mw = ctx.r(0.36)
    mh = ctx.r(0.24)

    # Chân đế
    stand_base = mpatches.Rectangle(
        (cx - ctx.r(0.040), y_base),
        ctx.r(0.080), ctx.r(0.012),
        color=MONITOR_BODY, zorder=6
    )
    ax.add_patch(stand_base); patches.append(stand_base)

    stand_neck = mpatches.Rectangle(
        (cx - ctx.r(0.009), y_base + ctx.r(0.012)),
        ctx.r(0.018), ctx.r(0.038),
        color=MONITOR_BODY, zorder=6
    )
    ax.add_patch(stand_neck); patches.append(stand_neck)

    # Thân màn hình
    mon = mpatches.FancyBboxPatch(
        (cx - mw / 2, y_base + ctx.r(0.050)),
        mw, mh,
        boxstyle="round,pad=0.006",
        color=MONITOR_BODY, zorder=6
    )
    ax.add_patch(mon); patches.append(mon)

    # Screen
    pad = ctx.r(0.014)
    screen_c = "#0A1628" if is_night else MONITOR_SCREEN
    screen = mpatches.Rectangle(
        (cx - mw / 2 + pad, y_base + ctx.r(0.050) + pad),
        mw - 2 * pad, mh - 2 * pad,
        color=screen_c, zorder=7
    )
    ax.add_patch(screen); patches.append(screen)

    # Nội dung màn hình
    glow_c = MONITOR_GLOW if is_night else "#64B5F6"
    np.random.seed(11)
    for i in range(6):
        sy = y_base + ctx.r(0.068) + i * ctx.r(0.030)
        if sy + ctx.r(0.012) > y_base + ctx.r(0.050) + mh - pad:
            break
        lw_ = ctx.r(np.random.uniform(0.06, 0.26))
        sl = mpatches.Rectangle(
            (cx - mw / 2 + pad + ctx.r(0.008), sy),
            lw_, ctx.r(0.011),
            color=glow_c, alpha=0.32 + i * 0.04, zorder=8
        )
        ax.add_patch(sl); patches.append(sl)

    # Glow màn hình (đêm / deadline)
    if is_night or variant == "deadline":
        glow = mpatches.FancyBboxPatch(
            (cx - mw / 2, y_base + ctx.r(0.050)),
            mw, mh,
            boxstyle="round,pad=0.006",
            color=MONITOR_GLOW, alpha=0.055, zorder=5
        )
        ax.add_patch(glow); patches.append(glow)


def _draw_coffee_cup(ax, patches, ctx: CanvasCtx,
                     nx: float, y_base: float, variant: str):
    """Ly cà phê trên bàn."""
    cx = ctx.x(nx)
    cw = ctx.r(0.042)
    ch = ctx.r(0.052)

    cup = mpatches.FancyBboxPatch(
        (cx - cw / 2, y_base + ctx.r(0.006)),
        cw, ch,
        boxstyle="round,pad=0.002",
        color="#ECEFF1", zorder=6
    )
    ax.add_patch(cup); patches.append(cup)

    # Quai
    handle = Arc(
        (cx + cw / 2 + ctx.r(0.010), y_base + ctx.r(0.032)),
        ctx.r(0.022), ctx.r(0.028),
        angle=0, theta1=270, theta2=90,
        color="#B0BEC5", lw=ctx.lw(0.014), zorder=6
    )
    ax.add_patch(handle); patches.append(handle)

    # Cà phê
    coffee_c = "#1A0A00" if variant == "deadline" else "#4E342E"
    coffee = mpatches.Rectangle(
        (cx - cw / 2 + ctx.r(0.005), y_base + ch * 0.55),
        cw - ctx.r(0.010), ch * 0.22,
        color=coffee_c, zorder=7
    )
    ax.add_patch(coffee); patches.append(coffee)

    # Khói (ngày / deadline)
    if variant != "night":
        for soff in [-0.012, 0.008]:
            sx = cx + ctx.r(soff)
            smoke = ax.plot(
                [sx, sx + ctx.r(0.005), sx - ctx.r(0.003)],
                [y_base + ch + ctx.r(0.010),
                 y_base + ch + ctx.r(0.025),
                 y_base + ch + ctx.r(0.038)],
                '-', color="#B0BEC5",
                lw=ctx.lw(0.010), alpha=0.5, zorder=6
            )[0]
            patches.append(smoke)


def _draw_papers(ax, patches, ctx: CanvasCtx,
                 nx: float, y_base: float, variant: str):
    """Đống giấy tờ."""
    cx = ctx.x(nx)
    pw = ctx.r(0.075)
    ph = ctx.r(0.095)

    offsets = [(0, 0, 0), (ctx.r(0.010), ctx.r(0.005), 5),
               (ctx.r(0.018), -ctx.r(0.003), -7)]
    if variant == "deadline":
        offsets += [(ctx.r(0.028), ctx.r(0.008), 12),
                    (-ctx.r(0.012), ctx.r(0.004), -5)]

    for dx, dy, angle in offsets:
        import matplotlib.transforms as transforms
        t = ax.transData
        p_cx = cx + dx + pw / 2
        p_cy = y_base + dy + ph / 2
        rot = transforms.Affine2D().rotate_deg_around(p_cx, p_cy, angle) + t
        paper = mpatches.FancyBboxPatch(
            (cx + dx, y_base + dy), pw, ph,
            boxstyle="square,pad=0",
            color="#FAFAFA", zorder=6,
            transform=rot
        )
        ax.add_patch(paper); patches.append(paper)

        for loff in [0.22, 0.42, 0.62]:
            pl = ax.plot(
                [cx + dx + ctx.r(0.010),
                 cx + dx + pw - ctx.r(0.010)],
                [y_base + dy + ph * loff,
                 y_base + dy + ph * loff],
                '-', color="#CFD8DC",
                lw=ctx.lw(0.006), alpha=0.55, zorder=7,
            )[0]
            patches.append(pl)


def _draw_desk_lamp(ax, patches, ctx: CanvasCtx,
                    nx: float, y_base: float, variant: str):
    """Đèn bàn."""
    lamp_on = variant in ("night", "deadline")
    cx = ctx.x(nx)

    # Đế
    base = mpatches.Rectangle(
        (cx - ctx.r(0.022), y_base + ctx.r(0.002)),
        ctx.r(0.044), ctx.r(0.009),
        color=LAMP_BASE, zorder=6
    )
    ax.add_patch(base); patches.append(base)

    # Cột
    pole = ax.plot(
        [cx, cx + ctx.r(0.028)],
        [y_base + ctx.r(0.011), y_base + ctx.r(0.095)],
        '-', color=LAMP_BASE,
        lw=ctx.lw(0.020), zorder=6
    )[0]
    patches.append(pole)

    # Chụp
    shade = mpatches.FancyBboxPatch(
        (cx + ctx.r(0.012), y_base + ctx.r(0.092)),
        ctx.r(0.062), ctx.r(0.034),
        boxstyle="round,pad=0.003",
        color=LAMP_BASE, zorder=6
    )
    ax.add_patch(shade); patches.append(shade)

    if lamp_on:
        glow = plt.Circle(
            (cx + ctx.r(0.043), y_base + ctx.r(0.092)),
            ctx.r(0.052),
            color=LAMP_GLOW, alpha=0.15, zorder=5
        )
        ax.add_patch(glow); patches.append(glow)


def _draw_wall_clock(ax, patches, ctx: CanvasCtx,
                     nx: float, ny: float):
    """Đồng hồ tường."""
    cx, cy = ctx.x(nx), ctx.y(ny)
    r = ctx.r(0.055)

    face = plt.Circle((cx, cy), r,
                       facecolor="#ECEFF1",
                       edgecolor="#90A4AE",
                       linewidth=ctx.lw(0.016), zorder=4)
    ax.add_patch(face); patches.append(face)

    # Kim giờ + phút
    hh = ax.plot([cx, cx - r * 0.35], [cy, cy + r * 0.38],
                 '-', color="#37474F",
                 lw=ctx.lw(0.018), zorder=5)[0]
    patches.append(hh)

    mh = ax.plot([cx, cx + r * 0.08], [cy, cy + r * 0.60],
                 '-', color="#37474F",
                 lw=ctx.lw(0.014), zorder=5)[0]
    patches.append(mh)

    center = plt.Circle((cx, cy), r * 0.08,
                         color="#E53935", zorder=6)
    ax.add_patch(center); patches.append(center)

    # 4 vạch giờ chính
    for ang in [90, 0, 270, 180]:
        a = np.radians(ang)
        tx = cx + (r - r * 0.12) * np.cos(a)
        ty = cy + (r - r * 0.12) * np.sin(a)
        tick = plt.Circle((tx, ty), r * 0.06,
                           color="#546E7A", zorder=5)
        ax.add_patch(tick); patches.append(tick)


def _draw_plant(ax, patches, ctx: CanvasCtx,
                nx: float, variant: str):
    """Cây xanh góc phòng."""
    is_night = variant == "night"
    cx       = ctx.x(nx)
    y_base   = ctx.ground_top

    pot_c  = "#6D4C41" if is_night else PLANT_POT
    leaf_c = "#1B5E20" if is_night else PLANT_LEAF

    pw = ctx.r(0.075)
    ph = ctx.r(0.058)

    # Chậu
    pot = mpatches.FancyBboxPatch(
        (cx - pw / 2, y_base), pw, ph,
        boxstyle="round,pad=0.004",
        color=pot_c, zorder=4
    )
    ax.add_patch(pot); patches.append(pot)

    # Đất
    soil = mpatches.Rectangle(
        (cx - pw / 2 + ctx.r(0.005), y_base + ph * 0.72),
        pw - ctx.r(0.010), ph * 0.20,
        color="#3E2723", zorder=5
    )
    ax.add_patch(soil); patches.append(soil)

    # Thân cây
    stem = ax.plot(
        [cx, cx], [y_base + ph, y_base + ph + ctx.r(0.090)],
        '-', color="#4E342E",
        lw=ctx.lw(0.022), zorder=5
    )[0]
    patches.append(stem)

    # Lá
    stem_top = y_base + ph + ctx.r(0.090)
    lr = ctx.r(0.038)
    for lx, ly, ldr in [
        (cx,            stem_top + lr * 0.85, 1.00),
        (cx - lr * 0.7, stem_top + lr * 0.50, 0.72),
        (cx + lr * 0.7, stem_top + lr * 0.45, 0.68),
        (cx - lr * 0.3, stem_top + lr * 1.30, 0.58),
        (cx + lr * 0.3, stem_top + lr * 1.25, 0.52),
    ]:
        lf = plt.Circle((lx, ly), lr * ldr,
                         color=leaf_c, alpha=0.92, zorder=5)
        ax.add_patch(lf); patches.append(lf)

        # ── Append vào cuối office.py ─────────────────────────────────────────────────



import math


def animate_background_office(ax, ctx, variant: str, t_sec: float) -> list:
    """
    Dynamic elements văn phòng — gọi mỗi frame.
    - Đồng hồ tường: kim giây quay
    - Màn hình: cursor nhấp nháy
    - Đèn bàn (night/deadline): glow pulse
    - Khói cà phê: wiggle
    """
    arts = []
    is_night    = variant == "night"
    is_deadline = variant == "deadline"

    # ── Kim giây đồng hồ ─────────────────────────────────────────────────────
    cx_clock  = ctx.x(0.50)
    cy_clock  = ctx.y(0.80)
    r_clock   = ctx.r(0.055)
    sec_angle = math.radians(90 - (t_sec % 60) * 6)
    sx = cx_clock + r_clock * 0.75 * math.cos(sec_angle)
    sy = cy_clock + r_clock * 0.75 * math.sin(sec_angle)
    sec_hand = ax.plot(
        [cx_clock, sx], [cy_clock, sy],
        "-", color="#E53935", lw=ctx.lw(0.010), zorder=6
    )[0]
    arts.append(sec_hand)

    # ── Cursor nhấp nháy trên màn hình (1Hz) ─────────────────────────────────
    if int(t_sec * 2) % 2 == 0:
        desk_y = ctx.zone_y("mid", 0.05)
        desk_h = ctx.r(0.032)
        pad    = ctx.r(0.014)
        cur_x  = ctx.x(0.50) - ctx.r(0.18) / 2 + pad + ctx.r(0.012)
        cur_y  = desk_y + desk_h + ctx.r(0.050) + pad + ctx.r(0.012)
        cursor = mpatches.Rectangle(
            (cur_x, cur_y), ctx.r(0.008), ctx.r(0.018),
            color="#4FC3F7" if is_night else "#64B5F6",
            alpha=0.9, zorder=9
        )
        ax.add_patch(cursor)
        arts.append(cursor)

    # ── Glow đèn bàn pulse (night / deadline) ────────────────────────────────
    if is_night or is_deadline:
        pulse = 0.13 + math.sin(t_sec * 2.5) * 0.025
        glow  = plt.Circle(
            (ctx.x(0.08) + ctx.r(0.043),
             ctx.zone_y("mid", 0.05) + ctx.r(0.032) + ctx.r(0.092)),
            ctx.r(pulse),
            color=LAMP_GLOW, alpha=0.12 + math.sin(t_sec * 2.5) * 0.03, zorder=5
        )
        ax.add_patch(glow)
        arts.append(glow)

    # ── Khói cà phê wiggle ────────────────────────────────────────────────────
    if variant != "night":
        desk_y = ctx.zone_y("mid", 0.05)
        desk_h = ctx.r(0.032)
        cup_cx = ctx.x(0.78)
        ch     = ctx.r(0.052)
        base_y = desk_y + desk_h + ch + ctx.r(0.010)
        for i, soff in enumerate([-0.012, 0.008]):
            sx_s = cup_cx + ctx.r(soff) + math.sin(t_sec * 3 + i) * ctx.r(0.008)
            smoke = ax.plot(
                [sx_s,
                 sx_s + ctx.r(0.006) * math.sin(t_sec * 2 + i + 1),
                 sx_s - ctx.r(0.004) * math.sin(t_sec * 2 + i)],
                [base_y, base_y + ctx.r(0.018), base_y + ctx.r(0.034)],
                "-", color="#B0BEC5", lw=ctx.lw(0.010), alpha=0.45, zorder=6
            )[0]
            arts.append(smoke)

    return arts
