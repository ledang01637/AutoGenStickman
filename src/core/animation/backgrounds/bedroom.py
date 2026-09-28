"""
Background: Bedroom (Phòng ngủ)
Canvas: scale tự động qua CanvasCtx (9:16 / 16:9 / 1:1)

Phù hợp với chủ đề:
  - Sáng dậy không muốn đi làm / đi học
  - Cuộc sống nằm giường cả ngày
  - Mất ngủ, lo âu đêm khuya
  - WFH, làm việc trên giường
  - Lazy Sunday, me time

Variants:
  morning — sáng sớm, ánh nắng qua rèm, năng lượng thấp
  night   — đêm khuya, đèn mờ, ánh điện thoại
  lazy    — ban ngày nhưng rèm kéo, chăn gối bừa bộn
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, Arc

from .canvas import CanvasCtx
from .utils import setup_ax, draw_floor_planks, draw_stars, draw_moon
import math

# ── Palette ───────────────────────────────────────────────────────────────────
WALL_MORNING = "#FFF8F0"
WALL_NIGHT   = "#12101E"
WALL_LAZY    = "#EDE8E0"

FLOOR_WOOD   = "#C8A882"
FLOOR_DARK   = "#A08860"

BED_FRAME    = "#6D4C41"
BED_SHEET    = "#E3F2FD"
BED_SHEET_N  = "#1A237E"
PILLOW_C     = "#FFFFFF"
PILLOW_N     = "#283593"
BLANKET_C    = "#BBDEFB"
BLANKET_N    = "#0D47A1"
BLANKET_L    = "#C8E6C9"

CURTAIN_L    = "#EF9A9A"   # rèm sáng
CURTAIN_N    = "#1A237E"   # rèm đêm
CURTAIN_LA   = "#A5D6A7"   # rèm lazy

DESK_COLOR   = "#8D6E63"
LAMP_BASE    = "#546E7A"
LAMP_GLOW    = "#FFF9C4"
SHELF_COLOR  = "#8D6E63"
BOOK_COLORS  = ["#E53935", "#1565C0", "#2E7D32", "#F57F17", "#6A1B9A"]
RUG_COLORS   = {"morning": "#EF9A9A", "night": "#1A237E", "lazy": "#A5D6A7"}
WINDOW_FRAME = "#8D6E63"


def build_background_bedroom(ax, ctx: CanvasCtx, variant: str = "morning"):
    """
    Vẽ background phòng ngủ. Tọa độ tự scale theo ctx.

    Args:
        ax      : matplotlib Axes
        ctx     : CanvasCtx — xác định canvas ratio + helpers
        variant : "morning" | "night" | "lazy"
    """
    patches = []
    setup_ax(ax, ctx)
    np.random.seed(42)

    is_night   = variant == "night"
    is_lazy    = variant == "lazy"
    is_morning = variant == "morning"

    wall_c  = WALL_NIGHT if is_night else (WALL_LAZY if is_lazy else WALL_MORNING)
    floor_c = "#0A0808"  if is_night else FLOOR_WOOD

    # ── Tường ─────────────────────────────────────────────────────────────────
    wall = mpatches.Rectangle(
        (0, ctx.ground_top), ctx.W, ctx.H - ctx.ground_top,
        color=wall_c, zorder=0
    )
    ax.add_patch(wall); patches.append(wall)

    # Chân tường
    skirting = mpatches.Rectangle(
        (0, ctx.ground_top - ctx.r(0.010)),
        ctx.W, ctx.r(0.010),
        color=BED_FRAME, alpha=0.40, zorder=2
    )
    ax.add_patch(skirting); patches.append(skirting)

    # ── Sàn ───────────────────────────────────────────────────────────────────
    floor = mpatches.Rectangle(
        (0, 0), ctx.W, ctx.ground_top,
        color=floor_c, zorder=1
    )
    ax.add_patch(floor); patches.append(floor)

    if not is_night:
        draw_floor_planks(ax, patches, ctx,
                          base_color=floor_c, plank_color=FLOOR_DARK,
                          n_lines=5, zorder=2)

    # Thảm phòng ngủ
    _draw_rug(ax, patches, ctx, variant=variant)

    # ── Cửa sổ + rèm ──────────────────────────────────────────────────────────
    _draw_window_curtain(ax, patches, ctx, nx=0.72, variant=variant)

    # ── Giường ────────────────────────────────────────────────────────────────
    _draw_bed(ax, patches, ctx, variant=variant)

    # ── Tủ đầu giường + đèn ngủ ───────────────────────────────────────────────
    _draw_nightstand(ax, patches, ctx, nx=0.88, variant=variant)

    # ── Kệ sách nhỏ ───────────────────────────────────────────────────────────
    _draw_shelf(ax, patches, ctx, nx=0.04, variant=variant)

    # ── Đồng hồ báo thức ──────────────────────────────────────────────────────
    _draw_alarm_clock(ax, patches, ctx, nx=0.86, variant=variant)

    # ── Poster tường ──────────────────────────────────────────────────────────
    _draw_poster(ax, patches, ctx, nx=0.22, variant=variant)

    # ── Overlay đêm ───────────────────────────────────────────────────────────
    if is_night:
        dark = mpatches.Rectangle(
            (0, 0), ctx.W, ctx.H,
            color="#05040F", alpha=0.45, zorder=8
        )
        ax.add_patch(dark); patches.append(dark)

        # Ánh sáng điện thoại glow phía dưới (stickman zone)
        phone_glow = plt.Circle(
            (ctx.x(0.50), ctx.ground_top + ctx.r(0.15)),
            ctx.r(0.18),
            color="#64B5F6", alpha=0.08, zorder=7
        )
        ax.add_patch(phone_glow); patches.append(phone_glow)

    # ── Ánh nắng sáng ─────────────────────────────────────────────────────────
    if is_morning:
        _draw_morning_light(ax, patches, ctx)

    return patches


# ── Helpers ───────────────────────────────────────────────────────────────────

def _draw_rug(ax, patches, ctx: CanvasCtx, variant: str):
    """Thảm tròn trước giường."""
    cx = ctx.x(0.38)
    cy = ctx.ground_top * 0.45
    rug_c = RUG_COLORS.get(variant, "#EF9A9A")

    rug = mpatches.Ellipse(
        (cx, cy), ctx.r(0.38), ctx.r(0.12),
        color=rug_c, alpha=0.55, zorder=2
    )
    ax.add_patch(rug); patches.append(rug)

    # Viền thảm
    rug_border = mpatches.Ellipse(
        (cx, cy), ctx.r(0.38), ctx.r(0.12),
        facecolor="none",
        edgecolor=rug_c,
        linewidth=ctx.lw(0.020),
        alpha=0.80, zorder=2
    )
    ax.add_patch(rug_border); patches.append(rug_border)


def _draw_window_curtain(ax, patches, ctx: CanvasCtx,
                         nx: float, variant: str):
    """Cửa sổ + rèm."""

    is_night = variant == "night"
    is_lazy = variant == "lazy"
    is_morning = variant == "morning"

    curtain_c = CURTAIN_N if is_night else (CURTAIN_LA if is_lazy else CURTAIN_L)
    sky_c     = "#05050F" if is_night else ("#D4C5A9" if is_lazy else "#87CEEB")

    ww = ctx.r(0.28)
    wh = ctx.r(0.38)
    cx = ctx.x(nx)
    cy_bot = ctx.zone_y("mid", 0.55)
    x  = cx - ww / 2

    # Nền trời / ngoài cửa sổ
    sky = mpatches.Rectangle(
        (x + ctx.r(0.008), cy_bot + ctx.r(0.008)),
        ww - ctx.r(0.016), wh - ctx.r(0.016),
        color=sky_c, zorder=3
    )
    ax.add_patch(sky); patches.append(sky)

    if is_night:
        # Sao + trăng nhỏ trong cửa sổ
        np.random.seed(13)
        for _ in range(10):
            sx = np.random.uniform(x + ctx.r(0.02), x + ww - ctx.r(0.02))
            sy = np.random.uniform(cy_bot + ctx.r(0.04), cy_bot + wh - ctx.r(0.03))
            st = ax.plot([sx], [sy], '*', color="#FFF9C4",
                         markersize=ctx.r(0.016) * 10,
                         alpha=np.random.uniform(0.4, 0.9), zorder=4)[0]
            patches.append(st)
        moon = plt.Circle(
            (cx - ctx.r(0.04), cy_bot + wh * 0.75),
            ctx.r(0.038),
            color="#FFF9C4", alpha=0.88, zorder=4
        )
        ax.add_patch(moon); patches.append(moon)
    elif is_morning:
        # Ánh nắng nhẹ qua cửa sổ
        sun_glow = plt.Circle(
            (cx + ctx.r(0.05), cy_bot + wh * 0.70),
            ctx.r(0.060),
            color="#FFD54F", alpha=0.30, zorder=4
        )
        ax.add_patch(sun_glow); patches.append(sun_glow)

    # Khung cửa sổ
    frame = FancyBboxPatch(
        (x, cy_bot), ww, wh,
        boxstyle="square,pad=0",
        edgecolor=WINDOW_FRAME,
        linewidth=ctx.lw(0.025),
        facecolor="none", zorder=6
    )
    ax.add_patch(frame); patches.append(frame)

    # Thanh chia
    mid_x = ax.plot([cx, cx],
                    [cy_bot + ctx.r(0.01), cy_bot + wh - ctx.r(0.01)],
                    '-', color=WINDOW_FRAME,
                    lw=ctx.lw(0.016), zorder=6)[0]
    patches.append(mid_x)

    # Rèm — 2 tấm, lazy/night kéo kín hơn
    open_frac = 0.12 if (is_lazy or is_night) else 0.28
    rw = ww * open_frac

    for side_x, anchor in [(x, x), (x + ww - rw, x + ww - rw)]:
        curtain = FancyBboxPatch(
            (side_x, cy_bot - ctx.r(0.01)), rw, wh + ctx.r(0.02),
            boxstyle="round,pad=0.004",
            color=curtain_c, alpha=0.90, zorder=7
        )
        ax.add_patch(curtain); patches.append(curtain)

        # Nếp rèm
        for fold_x in np.linspace(side_x + rw * 0.2, side_x + rw * 0.8, 3):
            fold = ax.plot(
                [fold_x, fold_x],
                [cy_bot, cy_bot + wh],
                '-', color=curtain_c,
                lw=ctx.lw(0.008), alpha=0.40, zorder=8
            )[0]
            patches.append(fold)

    # Thanh treo rèm
    rod = mpatches.Rectangle(
        (x - ctx.r(0.014), cy_bot + wh - ctx.r(0.014)),
        ww + ctx.r(0.028), ctx.r(0.014),
        color=BED_FRAME, zorder=8
    )
    ax.add_patch(rod); patches.append(rod)


def _draw_bed(ax, patches, ctx: CanvasCtx, variant: str):
    """Giường + chăn + gối."""
    is_night = variant == "night"
    is_lazy  = variant == "lazy"

    sheet_c   = BED_SHEET_N  if is_night else BED_SHEET
    pillow_c  = PILLOW_N     if is_night else PILLOW_C
    blanket_c = BLANKET_N    if is_night else (BLANKET_L if is_lazy else BLANKET_C)

    # Khung đầu giường (headboard) — gắn tường trái
    hb_w = ctx.r(0.62)
    hb_h = ctx.r(0.24)
    hb_x = ctx.x(0.04)
    hb_y = ctx.zone_y("ground", 0.55)

    headboard = FancyBboxPatch(
        (hb_x, hb_y), hb_w, hb_h,
        boxstyle="round,pad=0.008",
        color=BED_FRAME, zorder=3
    )
    ax.add_patch(headboard); patches.append(headboard)

    # Đệm giường
    mattress_y = ctx.ground_top * 0.30
    mattress_h = ctx.r(0.14)
    mattress   = FancyBboxPatch(
        (hb_x, mattress_y), hb_w, mattress_h,
        boxstyle="round,pad=0.006",
        color=sheet_c, zorder=4
    )
    ax.add_patch(mattress); patches.append(mattress)

    # Chăn — lazy thì vứt lung tung
    blanket_y = mattress_y + mattress_h * 0.25
    if is_lazy:
        # Chăn nhàu
        for i, (bx_off, by_off, bangle) in enumerate([
            (ctx.r(0.02),  ctx.r(0.01), 8),
            (ctx.r(0.10),  ctx.r(0.03), -5),
            (ctx.r(0.25),  ctx.r(0.00), 12),
        ]):
            import matplotlib.transforms as transforms
            b_cx = hb_x + bx_off + ctx.r(0.14)
            b_cy = blanket_y + by_off + ctx.r(0.06)
            rot = (transforms.Affine2D()
                   .rotate_deg_around(b_cx, b_cy, bangle)
                   + ax.transData)
            chunk = FancyBboxPatch(
                (hb_x + bx_off, blanket_y + by_off),
                ctx.r(0.28), ctx.r(0.12),
                boxstyle="round,pad=0.006",
                color=blanket_c, alpha=0.85,
                zorder=5, transform=rot
            )
            ax.add_patch(chunk); patches.append(chunk)
    else:
        blanket = FancyBboxPatch(
            (hb_x, blanket_y), hb_w * 0.72, ctx.r(0.10),
            boxstyle="round,pad=0.006",
            color=blanket_c, zorder=5
        )
        ax.add_patch(blanket); patches.append(blanket)

    # Gối — 2 cái
    pillow_y = mattress_y + mattress_h * 0.58
    for pi, px_off in enumerate([ctx.r(0.045), ctx.r(0.22)]):
        pillow = FancyBboxPatch(
            (hb_x + px_off, pillow_y),
            ctx.r(0.145), ctx.r(0.072),
            boxstyle="round,pad=0.006",
            color=pillow_c, zorder=6
        )
        ax.add_patch(pillow); patches.append(pillow)

    # Chân giường
    for fx in [hb_x + ctx.r(0.04), hb_x + hb_w - ctx.r(0.04)]:
        leg = mpatches.Rectangle(
            (fx - ctx.r(0.016), 0),
            ctx.r(0.032), mattress_y,
            color=BED_FRAME, zorder=3
        )
        ax.add_patch(leg); patches.append(leg)


def _draw_nightstand(ax, patches, ctx: CanvasCtx,
                     nx: float, variant: str):
    """Tủ đầu giường + đèn ngủ."""
    is_night = variant == "night"
    cx = ctx.x(nx)

    tw = ctx.r(0.14)
    th = ctx.r(0.10)
    ty = ctx.ground_top * 0.30   # ngang mặt đệm

    # Tủ
    stand = FancyBboxPatch(
        (cx - tw / 2, ty), tw, th,
        boxstyle="round,pad=0.005",
        color=BED_FRAME, zorder=4
    )
    ax.add_patch(stand); patches.append(stand)

    # Ngăn kéo
    drawer = FancyBboxPatch(
        (cx - tw / 2 + ctx.r(0.008), ty + th * 0.18),
        tw - ctx.r(0.016), th * 0.38,
        boxstyle="round,pad=0.003",
        color=DESK_COLOR, alpha=0.50, zorder=5
    )
    ax.add_patch(drawer); patches.append(drawer)

    # Tay nắm ngăn kéo
    knob = plt.Circle(
        (cx, ty + th * 0.37),
        ctx.r(0.010),
        color=LAMP_BASE, zorder=6
    )
    ax.add_patch(knob); patches.append(knob)

    # Đèn ngủ
    lamp_y = ty + th
    lamp_base = mpatches.Rectangle(
        (cx - ctx.r(0.018), lamp_y),
        ctx.r(0.036), ctx.r(0.008),
        color=LAMP_BASE, zorder=6
    )
    ax.add_patch(lamp_base); patches.append(lamp_base)

    pole = ax.plot(
        [cx, cx], [lamp_y + ctx.r(0.008), lamp_y + ctx.r(0.065)],
        '-', color=LAMP_BASE, lw=ctx.lw(0.014), zorder=6
    )[0]
    patches.append(pole)

    shade = FancyBboxPatch(
        (cx - ctx.r(0.038), lamp_y + ctx.r(0.065)),
        ctx.r(0.076), ctx.r(0.040),
        boxstyle="round,pad=0.004",
        color=LAMP_BASE, zorder=6
    )
    ax.add_patch(shade); patches.append(shade)

    if is_night or variant == "lazy":
        glow = plt.Circle(
            (cx, lamp_y + ctx.r(0.065)),
            ctx.r(0.065),
            color=LAMP_GLOW, alpha=0.18, zorder=5
        )
        ax.add_patch(glow); patches.append(glow)


def _draw_shelf(ax, patches, ctx: CanvasCtx,
                nx: float, variant: str):
    """Kệ sách nhỏ trên tường."""
    is_night = variant == "night"
    shelf_c  = "#3E2723" if is_night else SHELF_COLOR

    sw = ctx.r(0.22)
    sh = ctx.r(0.22)
    x  = ctx.x(nx)
    y  = ctx.zone_y("mid", 0.40)

    # Thân kệ mờ
    back = mpatches.Rectangle(
        (x, y), sw, sh,
        color=shelf_c, alpha=0.20, zorder=3
    )
    ax.add_patch(back); patches.append(back)

    # 2 tầng kệ
    plank_h = ctx.r(0.010)
    for fi in range(2):
        py = y + sh * fi / 2
        plank = mpatches.Rectangle(
            (x, py), sw, plank_h,
            color=shelf_c, zorder=4
        )
        ax.add_patch(plank); patches.append(plank)

    # Sách + đồ trang trí
    np.random.seed(55)
    for fi in range(2):
        bx = x + ctx.r(0.006)
        shelf_y = y + sh * fi / 2 + plank_h + ctx.r(0.003)
        while bx < x + sw - ctx.r(0.012):
            bw_ = ctx.r(np.random.uniform(0.012, 0.020))
            bh_ = ctx.r(np.random.uniform(0.026, 0.042))
            bc  = "#1A1A2E" if is_night else BOOK_COLORS[np.random.randint(len(BOOK_COLORS))]
            book = mpatches.Rectangle(
                (bx, shelf_y), bw_, bh_,
                color=bc, zorder=5
            )
            ax.add_patch(book); patches.append(book)
            bx += bw_ + ctx.r(0.004)


def _draw_alarm_clock(ax, patches, ctx: CanvasCtx,
                      nx: float, variant: str):
    """Đồng hồ báo thức trên tủ đầu giường."""
    is_night = variant == "night"
    cx = ctx.x(nx)
    ty = ctx.ground_top * 0.30
    th = ctx.r(0.10)
    y  = ty + th + ctx.r(0.002)

    r = ctx.r(0.030)
    body_c = "#37474F" if is_night else "#455A64"

    # Thân đồng hồ
    body = plt.Circle(
        (cx - ctx.r(0.020), y + r),
        r, facecolor=body_c,
        edgecolor="#263238",
        linewidth=ctx.lw(0.012), zorder=7
    )
    ax.add_patch(body); patches.append(body)

    # Mặt đồng hồ
    face = plt.Circle(
        (cx - ctx.r(0.020), y + r),
        r * 0.78,
        facecolor="#ECEFF1" if not is_night else "#1A237E",
        zorder=8
    )
    ax.add_patch(face); patches.append(face)

    # Kim
    clock_cx = cx - ctx.r(0.020)
    clock_cy = y + r
    hh = ax.plot(
        [clock_cx, clock_cx - r * 0.30],
        [clock_cy, clock_cy + r * 0.35],
        '-', color="#37474F", lw=ctx.lw(0.012), zorder=9
    )[0]
    patches.append(hh)

    mh = ax.plot(
        [clock_cx, clock_cx + r * 0.12],
        [clock_cy, clock_cy + r * 0.52],
        '-', color="#37474F", lw=ctx.lw(0.010), zorder=9
    )[0]
    patches.append(mh)

    # Chuông
    for bell_x in [cx - ctx.r(0.020) - r * 1.1, cx - ctx.r(0.020) + r * 1.1]:
        bell = plt.Circle(
            (bell_x, y + r * 1.6),
            r * 0.28, color=body_c, zorder=7
        )
        ax.add_patch(bell); patches.append(bell)


def _draw_poster(ax, patches, ctx: CanvasCtx,
                 nx: float, variant: str):
    """Poster / tranh treo tường."""
    is_night = variant == "night"
    cx = ctx.x(nx)

    pw = ctx.r(0.22)
    ph = ctx.r(0.28)
    y  = ctx.zone_y("mid", 0.50)
    x  = cx - pw / 2

    # Khung tranh
    frame = FancyBboxPatch(
        (x - ctx.r(0.008), y - ctx.r(0.008)),
        pw + ctx.r(0.016), ph + ctx.r(0.016),
        boxstyle="round,pad=0.005",
        color=BED_FRAME, zorder=3
    )
    ax.add_patch(frame); patches.append(frame)

    # Nền poster
    poster_colors = {
        "morning": "#FFF3E0",
        "night":   "#0D1B2A",
        "lazy":    "#F1F8E9",
    }
    poster = mpatches.Rectangle(
        (x, y), pw, ph,
        color=poster_colors.get(variant, "#FFF3E0"),
        zorder=4
    )
    ax.add_patch(poster); patches.append(poster)

    # Nội dung poster — hình đơn giản
    if is_night:
        # Moon + stars poster
        p_moon = plt.Circle(
            (cx, y + ph * 0.60), ctx.r(0.042),
            color="#FFF9C4", alpha=0.90, zorder=5
        )
        ax.add_patch(p_moon); patches.append(p_moon)
        np.random.seed(99)
        for _ in range(8):
            sx = np.random.uniform(x + ctx.r(0.02), x + pw - ctx.r(0.02))
            sy = np.random.uniform(y + ctx.r(0.02), y + ph * 0.85)
            st = ax.plot([sx], [sy], '*', color="#FFF9C4",
                         markersize=ctx.r(0.012) * 10,
                         alpha=np.random.uniform(0.4, 0.8), zorder=5)[0]
            patches.append(st)
    else:
        # Mountain / landscape poster
        mountain_c = "#A5D6A7" if variant == "lazy" else "#90CAF9"
        tri = mpatches.Polygon(
            [(cx, y + ph * 0.82),
             (x + pw * 0.15, y + ph * 0.35),
             (x + pw * 0.85, y + ph * 0.35)],
            color=mountain_c, alpha=0.70, zorder=5
        )
        ax.add_patch(tri); patches.append(tri)

        sun_p = plt.Circle(
            (cx + pw * 0.25, y + ph * 0.75),
            ctx.r(0.022),
            color="#FFD54F", alpha=0.80, zorder=5
        )
        ax.add_patch(sun_p); patches.append(sun_p)


def _draw_morning_light(ax, patches, ctx: CanvasCtx):
    """Luồng ánh nắng sáng qua rèm."""
    # Diagonal light beam từ cửa sổ xuống sàn
    beam_c = "#FFD54F"
    for i, alpha in enumerate([0.06, 0.04, 0.025]):
        offset = ctx.r(i * 0.022)
        beam = mpatches.Polygon(
            [
                (ctx.x(0.62) + offset, ctx.zone_y("mid", 0.55)),
                (ctx.x(0.82) - offset, ctx.zone_y("mid", 0.55)),
                (ctx.x(0.72) + offset * 2, ctx.ground_top),
                (ctx.x(0.52) - offset * 2, ctx.ground_top),
            ],
            color=beam_c, alpha=alpha, zorder=1
        )
        ax.add_patch(beam); patches.append(beam)



def animate_background_bedroom(ax, ctx, variant: str, t_sec: float) -> list:
    """
    Dynamic elements phòng ngủ:
    - Ánh điện thoại pulse (night)
    - Đèn ngủ glow pulse (night / lazy)
    - Beam nắng pulse + rèm lay (morning)
    """
    arts = []

    # ── Ánh điện thoại pulse (night) ─────────────────────────────────────────
    if variant == "night":
        pulse      = 0.06 + math.sin(t_sec * 1.2) * 0.025
        phone_glow = plt.Circle(
            (ctx.x(0.50), ctx.ground_top + ctx.r(0.15)),
            ctx.r(pulse + 0.15), color="#64B5F6", alpha=pulse, zorder=7
        )
        ax.add_patch(phone_glow)
        arts.append(phone_glow)

    # ── Đèn ngủ glow pulse (night / lazy) ────────────────────────────────────
    if variant in ("night", "lazy"):
        pulse_a = 0.15 + math.sin(t_sec * 1.5) * 0.04
        glow    = plt.Circle(
            (ctx.x(0.88), ctx.ground_top * 0.30 + ctx.r(0.10) + ctx.r(0.065)),
            ctx.r(0.068), color="#FFF9C4", alpha=pulse_a, zorder=5
        )
        ax.add_patch(glow)
        arts.append(glow)

    # ── Beam nắng pulse + rèm lay (morning) ──────────────────────────────────
    if variant == "morning":
        beam_alpha = 0.05 + math.sin(t_sec * 0.8) * 0.015
        beam = mpatches.Polygon(
            [(ctx.x(0.62), ctx.zone_y("mid", 0.55)),
             (ctx.x(0.82), ctx.zone_y("mid", 0.55)),
             (ctx.x(0.72) + ctx.r(0.04), ctx.ground_top),
             (ctx.x(0.52) - ctx.r(0.04), ctx.ground_top)],
            color="#FFD54F", alpha=beam_alpha, zorder=1
        )
        ax.add_patch(beam)
        arts.append(beam)

        ww     = ctx.r(0.28)
        wh     = ctx.r(0.38)
        cx     = ctx.x(0.72)
        cy_bot = ctx.zone_y("mid", 0.55)
        rw     = ww * 0.28
        sway   = math.sin(t_sec * 1.2) * ctx.r(0.008)
        for side_x in [cx - ww / 2, cx + ww / 2 - rw]:
            curtain = mpatches.FancyBboxPatch(
                (side_x + sway, cy_bot - ctx.r(0.01)),
                rw, wh + ctx.r(0.02),
                boxstyle="round,pad=0.004",
                color="#EF9A9A", alpha=0.90, zorder=7
            )
            ax.add_patch(curtain)
            arts.append(curtain)

    return arts