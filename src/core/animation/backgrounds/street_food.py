"""
Background: Street Food (Quán ăn vỉa hè)
Canvas: scale tự động qua CanvasCtx (9:16 / 16:9 / 1:1)

Phù hợp với chủ đề:
  - Ăn trưa vội vã giữa ca làm
  - Ăn đêm muộn sau khi tan ca / nhậu về
  - Cuối tuần la cà hàng quán
  - Review đồ ăn vỉa hè
  - Nỗi nhớ quê / ẩm thực đường phố

Variants:
  lunch   — trưa nắng, hàng đông, khói bốc nghi ngút
  night   — đêm khuya, đèn vàng, bóng đèn trang trí
  weekend — sáng sớm cuối tuần, sương mù nhẹ, không đông
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch

from .canvas import CanvasCtx
from .utils import setup_ax, draw_floor_planks, gradient_rect
import math

# ── Palette ───────────────────────────────────────────────────────────────────
SKY_LUNCH_TOP    = "#87CEEB"
SKY_LUNCH_BOT    = "#B0E0FF"
SKY_NIGHT_TOP    = "#0A0818"
SKY_NIGHT_BOT    = "#1A1535"
SKY_WEEKEND_TOP  = "#C9D8E8"
SKY_WEEKEND_BOT  = "#E8EEF4"

GROUND_LUNCH     = "#C2B49A"
GROUND_NIGHT     = "#1A1614"
GROUND_WEEKEND   = "#D4C9B5"

TARP_LUNCH       = "#E53935"   # bạt đỏ
TARP_NIGHT       = "#F57F17"   # bạt vàng cam
TARP_WEEKEND     = "#1565C0"   # bạt xanh navy
TARP_STRIPE      = "#FFFFFF"

POLE_COLOR       = "#5D4037"
TABLE_COLOR      = "#8D6E63"
STOOL_COLOR      = "#6D4C41"
BOWL_RIM         = "#D7CCC8"
BOWL_SOUP        = "#FF8F00"
STEAM_COLOR      = "#ECEFF1"

SIGN_BG_L        = "#FFEE58"
SIGN_BG_N        = "#FF6F00"
SIGN_BG_W        = "#E3F2FD"
SIGN_TEXT        = "#B71C1C"

LAMP_CORD        = "#5D4037"
LAMP_BULB        = "#FFF9C4"
LAMP_GLOW_L      = "#FFD54F"
LAMP_GLOW_N      = "#FF8F00"

SMOKE_COLOR      = "#CFD8DC"
CHARCOAL_COLOR   = "#37474F"
FLAME_COLOR      = "#FF6D00"

TREE_TRUNK       = "#5D4037"
TREE_LEAF        = "#388E3C"

ROAD_COLOR       = "#6D6D6D"
SIDEWALK_COLOR   = "#B0A898"
CURB_COLOR       = "#9E9E9E"


def build_background_street_food(ax, ctx: CanvasCtx, variant: str = "lunch"):
    """
    Vẽ background quán ăn vỉa hè. Tọa độ tự scale theo ctx.

    Args:
        ax      : matplotlib Axes
        ctx     : CanvasCtx
        variant : "lunch" | "night" | "weekend"

    Layout (9:16):
        y 0.00 → 0.19 : mặt đường + vỉa hè (ground zone)
        y 0.19 → 0.68 : không gian quán — bàn, bếp, bạt, khách (mid zone)
        y 0.68 → 1.00 : bầu trời + backdrop tường / phố (sky zone)
    """
    patches = []
    setup_ax(ax, ctx)
    np.random.seed(42)

    is_lunch   = variant == "lunch"
    is_night   = variant == "night"
    is_weekend = variant == "weekend"

    # ── Bầu trời ──────────────────────────────────────────────────────────────
    if is_night:
        gradient_rect(ax, patches, SKY_NIGHT_TOP, SKY_NIGHT_BOT,
                      y_bot=ctx.sky_bot, y_top=ctx.sky_top,
                      width=ctx.W, steps=28, zorder=0)
        _draw_night_sky(ax, patches, ctx)
    elif is_weekend:
        gradient_rect(ax, patches, SKY_WEEKEND_TOP, SKY_WEEKEND_BOT,
                      y_bot=ctx.sky_bot, y_top=ctx.sky_top,
                      width=ctx.W, steps=22, zorder=0)
        _draw_weekend_mist(ax, patches, ctx)
    else:  # lunch
        gradient_rect(ax, patches, SKY_LUNCH_TOP, SKY_LUNCH_BOT,
                      y_bot=ctx.sky_bot, y_top=ctx.sky_top,
                      width=ctx.W, steps=22, zorder=0)
        _draw_lunch_sun(ax, patches, ctx)

    # ── Tường / backdrop phía sau ──────────────────────────────────────────────
    _draw_backdrop_wall(ax, patches, ctx, variant=variant)

    # ── Mặt đường + vỉa hè ────────────────────────────────────────────────────
    _draw_road_sidewalk(ax, patches, ctx, variant=variant)

    # ── Bạt che (mái hiên) ────────────────────────────────────────────────────
    _draw_tarp_awning(ax, patches, ctx, variant=variant)

    # ── Bảng hiệu quán ────────────────────────────────────────────────────────
    _draw_sign(ax, patches, ctx, variant=variant)

    # ── Bếp than / lò nấu ────────────────────────────────────────────────────
    _draw_stove(ax, patches, ctx, variant=variant)

    # ── Bàn + ghế đẩu ────────────────────────────────────────────────────────
    _draw_table_stools(ax, patches, ctx, nx=0.38, variant=variant)

    # ── Tô / bát trên bàn ────────────────────────────────────────────────────
    _draw_bowls(ax, patches, ctx, variant=variant)

    # ── Cây nhỏ / chậu cây vỉa hè ────────────────────────────────────────────
    _draw_sidewalk_plant(ax, patches, ctx, nx=0.88, variant=variant)

    # ── Đèn trang trí ─────────────────────────────────────────────────────────
    _draw_string_lights(ax, patches, ctx, variant=variant)

    # ── Overlay đêm ───────────────────────────────────────────────────────────
    if is_night:
        dark = mpatches.Rectangle(
            (0, 0), ctx.W, ctx.H,
            color="#07060F", alpha=0.38, zorder=8
        )
        ax.add_patch(dark); patches.append(dark)

        # Hào quang đèn sợi đốt xuống quán
        glow = mpatches.Ellipse(
            (ctx.x(0.50), ctx.zone_y("mid", 0.70)),
            ctx.r(0.90), ctx.r(0.35),
            color=LAMP_GLOW_N, alpha=0.10, zorder=7
        )
        ax.add_patch(glow); patches.append(glow)

    return patches


# ── Sky details ───────────────────────────────────────────────────────────────

def _draw_night_sky(ax, patches, ctx: CanvasCtx):
    """Sao + trăng lưỡi liềm đêm khuya."""
    np.random.seed(17)
    for _ in range(22):
        sx = np.random.uniform(0.02, 0.98)
        sy = np.random.uniform(0.70, 0.98)
        sz = np.random.uniform(1.2, 3.0)
        al = np.random.uniform(0.35, 0.85)
        st = ax.plot([ctx.x(sx)], [ctx.y(sy)], '*',
                     color="#FFF9C4", markersize=sz, alpha=al, zorder=1)[0]
        patches.append(st)

    # Trăng lưỡi liềm
    moon_cx = ctx.x(0.82)
    moon_cy = ctx.y(0.90)
    mr = ctx.r(0.040)
    moon = plt.Circle((moon_cx, moon_cy), mr,
                       color="#FFF9C4", alpha=0.90, zorder=2)
    ax.add_patch(moon); patches.append(moon)
    moon_cut = plt.Circle((moon_cx + mr * 0.45, moon_cy + mr * 0.10),
                           mr * 0.80,
                           color=SKY_NIGHT_TOP, alpha=1.0, zorder=3)
    ax.add_patch(moon_cut); patches.append(moon_cut)


def _draw_lunch_sun(ax, patches, ctx: CanvasCtx):
    """Mặt trời trưa cao, nắng chói."""
    cx, cy = ctx.x(0.85), ctx.y(0.93)
    r = ctx.r(0.042)

    glow = plt.Circle((cx, cy), r * 1.8,
                       color="#FFD54F", alpha=0.18, zorder=1)
    ax.add_patch(glow); patches.append(glow)

    sun = plt.Circle((cx, cy), r,
                      color="#FFD54F", alpha=0.95, zorder=2)
    ax.add_patch(sun); patches.append(sun)


def _draw_weekend_mist(ax, patches, ctx: CanvasCtx):
    """Sương nhẹ buổi sáng cuối tuần."""
    mist = mpatches.Rectangle(
        (0, ctx.sky_bot), ctx.W, ctx.zone_h("sky") * 0.30,
        color="#FFFFFF", alpha=0.22, zorder=1
    )
    ax.add_patch(mist); patches.append(mist)


# ── Backdrop wall ─────────────────────────────────────────────────────────────

def _draw_backdrop_wall(ax, patches, ctx: CanvasCtx, variant: str):
    """Tường nhà / mặt tiền phía sau quán."""
    is_night = variant == "night"
    wall_c = "#1C1A2E" if is_night else ("#EDE8E0" if variant == "weekend" else "#F5EFE6")

    # Thân tường (mid zone trên)
    wall = mpatches.Rectangle(
        (0, ctx.zone_y("mid", 0.55)),
        ctx.W, ctx.zone_h("mid") * 0.50,
        color=wall_c, zorder=1
    )
    ax.add_patch(wall); patches.append(wall)

    # Gạch / ô tường gợi ý
    brick_c = "#BDB0A0" if not is_night else "#2A2840"
    np.random.seed(33)
    for row in range(3):
        ry = ctx.zone_y("mid", 0.58 + row * 0.125)
        offset = ctx.r(0.06) if row % 2 == 1 else 0
        for col in range(8):
            bx = col * ctx.r(0.12) + offset - ctx.r(0.06)
            bw = ctx.r(0.10)
            bh = ctx.r(0.022)
            brick = FancyBboxPatch(
                (bx, ry), bw, bh,
                boxstyle="square,pad=0",
                edgecolor=brick_c,
                linewidth=ctx.lw(0.006),
                facecolor="none", zorder=2
            )
            ax.add_patch(brick); patches.append(brick)

    # Cửa sổ nhỏ tòa nhà phía sau
    win_c = "#FFE082" if is_night else "#87CEEB"
    for wx in [0.12, 0.42, 0.70]:
        win = FancyBboxPatch(
            (ctx.x(wx), ctx.zone_y("mid", 0.74)),
            ctx.r(0.08), ctx.r(0.10),
            boxstyle="square,pad=0",
            facecolor=win_c,
            edgecolor="#6D4C41",
            linewidth=ctx.lw(0.012),
            alpha=0.80 if is_night else 0.65, zorder=3
        )
        ax.add_patch(win); patches.append(win)


# ── Road & sidewalk ───────────────────────────────────────────────────────────

def _draw_road_sidewalk(ax, patches, ctx: CanvasCtx, variant: str):
    """Vỉa hè + mặt đường (không có xe theo design decision)."""
    is_night = variant == "night"
    road_c    = "#3A3A3A" if is_night else ROAD_COLOR
    sidewalk_c = "#2A2620" if is_night else SIDEWALK_COLOR

    # Mặt đường dọc phía dưới
    road = mpatches.Rectangle(
        (0, 0), ctx.W, ctx.ground_top * 0.52,
        color=road_c, zorder=1
    )
    ax.add_patch(road); patches.append(road)

    # Vỉa hè
    sidewalk = mpatches.Rectangle(
        (0, ctx.ground_top * 0.52), ctx.W, ctx.ground_top * 0.48,
        color=sidewalk_c, zorder=2
    )
    ax.add_patch(sidewalk); patches.append(sidewalk)

    # Gờ vỉa hè
    curb = mpatches.Rectangle(
        (0, ctx.ground_top * 0.50), ctx.W, ctx.r(0.010),
        color=CURB_COLOR, alpha=0.60, zorder=3
    )
    ax.add_patch(curb); patches.append(curb)

    # Vân gạch vỉa hè
    if not is_night:
        draw_floor_planks(ax, patches, ctx,
                          base_color=sidewalk_c, plank_color="#A09080",
                          n_lines=3, zorder=3)

    # Vạch kẻ đường mờ
    for lx in [0.25, 0.55, 0.78]:
        dash = mpatches.Rectangle(
            (ctx.x(lx), ctx.ground_top * 0.22),
            ctx.r(0.06), ctx.r(0.008),
            color="#FFFFFF", alpha=0.30, zorder=2
        )
        ax.add_patch(dash); patches.append(dash)


# ── Tarp awning ───────────────────────────────────────────────────────────────

def _draw_tarp_awning(ax, patches, ctx: CanvasCtx, variant: str):
    """Bạt che vỉa hè — mái hiên đặc trưng quán ăn vỉa hè VN."""
    is_night = variant == "night"
    is_lunch = variant == "lunch"

    tarp_c  = TARP_NIGHT if is_night else (TARP_LUNCH if is_lunch else TARP_WEEKEND)
    pole_c  = POLE_COLOR

    pole_h  = ctx.zone_h("mid") * 0.72
    pole_w  = ctx.r(0.018)

    # Cột trụ bạt — 2 cột
    pole_xs = [ctx.x(0.04), ctx.x(0.92)]
    tarp_top_y = ctx.zone_y("mid", 0.72)

    for px in pole_xs:
        pole = mpatches.Rectangle(
            (px - pole_w / 2, ctx.ground_top),
            pole_w, pole_h,
            color=pole_c, zorder=4
        )
        ax.add_patch(pole); patches.append(pole)

    # Mái bạt — hình thang dốc nhẹ
    tarp_left  = ctx.x(0.01)
    tarp_right = ctx.x(0.99)
    tarp_bot_y = tarp_top_y - ctx.r(0.06)

    tarp = mpatches.Polygon(
        [
            (tarp_left,  tarp_top_y + ctx.r(0.04)),
            (tarp_right, tarp_top_y),
            (tarp_right, tarp_bot_y),
            (tarp_left,  tarp_bot_y - ctx.r(0.02)),
        ],
        color=tarp_c, alpha=0.92, zorder=5
    )
    ax.add_patch(tarp); patches.append(tarp)

    # Sọc kẻ bạt (gợi nhớ bạt bán hàng VN)
    np.random.seed(7)
    for i in range(6):
        sx = tarp_left + (tarp_right - tarp_left) * (i + 0.5) / 6
        stripe = ax.plot(
            [sx, sx],
            [tarp_bot_y - ctx.r(0.02), tarp_top_y + ctx.r(0.04)],
            '-', color=TARP_STRIPE,
            lw=ctx.lw(0.012), alpha=0.25, zorder=6
        )[0]
        patches.append(stripe)

    # Diềm bạt lắc lư (tam giác nhỏ)
    fringe_y = tarp_bot_y - ctx.r(0.008)
    fringe_h = ctx.r(0.028)
    n_fringe = 10
    for fi in range(n_fringe):
        fx = tarp_left + (tarp_right - tarp_left) * fi / n_fringe
        fw = (tarp_right - tarp_left) / n_fringe
        fringe = mpatches.Polygon(
            [
                (fx,            fringe_y),
                (fx + fw,       fringe_y),
                (fx + fw / 2,   fringe_y - fringe_h),
            ],
            color=tarp_c, alpha=0.75, zorder=6
        )
        ax.add_patch(fringe); patches.append(fringe)


# ── Sign ──────────────────────────────────────────────────────────────────────

def _draw_sign(ax, patches, ctx: CanvasCtx, variant: str):
    """Bảng hiệu quán treo trên bạt."""
    is_night = variant == "night"
    is_lunch = variant == "lunch"

    sign_bg = SIGN_BG_N if is_night else (SIGN_BG_L if is_lunch else SIGN_BG_W)

    sw = ctx.r(0.28)
    sh = ctx.r(0.075)
    sx = ctx.x(0.50) - sw / 2
    sy = ctx.zone_y("mid", 0.76)

    # Nền bảng
    sign_bg_p = FancyBboxPatch(
        (sx, sy), sw, sh,
        boxstyle="round,pad=0.006",
        facecolor=sign_bg,
        edgecolor=SIGN_TEXT,
        linewidth=ctx.lw(0.018),
        alpha=0.95, zorder=7
    )
    ax.add_patch(sign_bg_p); patches.append(sign_bg_p)

    # Chữ bảng hiệu
    sign_texts = {
        "lunch":   "PHỞ BÒ",
        "night":   "BÚN ĐẬU",
        "weekend": "BÁNh MÌ",
    }
    label = sign_texts.get(variant, "QUÁN ĂN")
    ax.text(
        ctx.x(0.50), sy + sh * 0.52,
        label,
        fontsize=ctx.r(0.048) * 10,
        color=SIGN_TEXT,
        ha="center", va="center",
        fontweight="bold", zorder=8
    )

    # Dây treo bảng
    for hx in [sx + sw * 0.20, sx + sw * 0.80]:
        cord = ax.plot(
            [hx, hx], [sy + sh, sy + sh + ctx.r(0.04)],
            '-', color=LAMP_CORD,
            lw=ctx.lw(0.010), zorder=6
        )[0]
        patches.append(cord)


# ── Stove / charcoal grill ────────────────────────────────────────────────────

def _draw_stove(ax, patches, ctx: CanvasCtx, variant: str):
    """Bếp than / lò nấu đặc trưng vỉa hè."""
    is_night = variant == "night"

    stove_x = ctx.x(0.74)
    stove_y = ctx.ground_top + ctx.r(0.005)
    sw = ctx.r(0.14)
    sh = ctx.r(0.10)

    # Thân bếp
    stove = FancyBboxPatch(
        (stove_x - sw / 2, stove_y), sw, sh,
        boxstyle="round,pad=0.005",
        facecolor=CHARCOAL_COLOR,
        edgecolor="#263238",
        linewidth=ctx.lw(0.014),
        zorder=5
    )
    ax.add_patch(stove); patches.append(stove)

    # Ghi bếp (thanh sắt)
    for gi in range(3):
        gx = stove_x - sw * 0.35 + gi * sw * 0.35
        grate = ax.plot(
            [gx, gx],
            [stove_y + sh * 0.55, stove_y + sh * 0.95],
            '-', color="#546E7A",
            lw=ctx.lw(0.014), zorder=6
        )[0]
        patches.append(grate)

    # Than hồng / lửa
    if variant in ("lunch", "night"):
        ember = mpatches.Ellipse(
            (stove_x, stove_y + sh * 0.30),
            sw * 0.55, sh * 0.22,
            color=FLAME_COLOR, alpha=0.75, zorder=6
        )
        ax.add_patch(ember); patches.append(ember)

        flame_glow = plt.Circle(
            (stove_x, stove_y + sh * 0.38),
            ctx.r(0.030),
            color="#FFD54F", alpha=0.30, zorder=5
        )
        ax.add_patch(flame_glow); patches.append(flame_glow)

    # Nồi / chảo trên bếp
    pot_r = ctx.r(0.052)
    pot = mpatches.Ellipse(
        (stove_x, stove_y + sh + pot_r * 0.40),
        pot_r * 2.0, pot_r * 0.60,
        color="#546E7A", zorder=7
    )
    ax.add_patch(pot); patches.append(pot)

    pot_side = FancyBboxPatch(
        (stove_x - pot_r, stove_y + sh + pot_r * 0.10),
        pot_r * 2.0, pot_r * 0.55,
        boxstyle="round,pad=0.003",
        facecolor="#455A64",
        edgecolor="#263238",
        linewidth=ctx.lw(0.010), zorder=6
    )
    ax.add_patch(pot_side); patches.append(pot_side)

    # Khói bốc lên từ nồi
    _draw_smoke(ax, patches, ctx,
                cx=stove_x, base_y=stove_y + sh + pot_r * 0.80,
                n_puffs=4, variant=variant)


def _draw_smoke(ax, patches, ctx: CanvasCtx,
                cx: float, base_y: float,
                n_puffs: int, variant: str):
    """Khói bốc lên từ nồi."""
    is_night = variant == "night"
    smoke_c  = "#90A4AE" if is_night else STEAM_COLOR
    np.random.seed(9)
    for i in range(n_puffs):
        sy = base_y + i * ctx.r(0.055)
        sx = cx + np.random.uniform(-ctx.r(0.02), ctx.r(0.02))
        sr = ctx.r(0.020 + i * 0.008)
        puff = plt.Circle(
            (sx, sy), sr,
            color=smoke_c,
            alpha=max(0.05, 0.38 - i * 0.08),
            zorder=7
        )
        ax.add_patch(puff); patches.append(puff)


# ── Table & stools ────────────────────────────────────────────────────────────

def _draw_table_stools(ax, patches, ctx: CanvasCtx,
                       nx: float, variant: str):
    """Bàn nhựa thấp + ghế đẩu vỉa hè."""
    is_night = variant == "night"
    table_c  = "#BDBDBD" if not is_night else "#424242"
    stool_c  = "#E53935" if variant == "lunch" else ("#1565C0" if variant == "weekend" else "#FF8F00")

    cx   = ctx.x(nx)
    ty   = ctx.ground_top + ctx.r(0.005)
    tw   = ctx.r(0.20)
    th   = ctx.r(0.060)
    tleg = ctx.r(0.040)

    # Mặt bàn
    table = FancyBboxPatch(
        (cx - tw / 2, ty + tleg), tw, th,
        boxstyle="round,pad=0.005",
        facecolor=table_c,
        edgecolor="#9E9E9E",
        linewidth=ctx.lw(0.012), zorder=5
    )
    ax.add_patch(table); patches.append(table)

    # Chân bàn
    for lx in [cx - tw * 0.38, cx + tw * 0.38]:
        leg = mpatches.Rectangle(
            (lx - ctx.r(0.006), ty), ctx.r(0.012), tleg,
            color="#757575", zorder=5
        )
        ax.add_patch(leg); patches.append(leg)

    # Ghế đẩu — 2 cái hai bên
    stool_h = ctx.r(0.042)
    stool_w = ctx.r(0.065)
    for sx_off in [-tw * 0.62, tw * 0.62]:
        stool = FancyBboxPatch(
            (cx + sx_off - stool_w / 2, ty),
            stool_w, stool_h,
            boxstyle="round,pad=0.004",
            facecolor=stool_c,
            edgecolor="#B71C1C" if variant == "lunch" else "#0D47A1",
            linewidth=ctx.lw(0.010), alpha=0.88, zorder=5
        )
        ax.add_patch(stool); patches.append(stool)


# ── Bowls ─────────────────────────────────────────────────────────────────────

def _draw_bowls(ax, patches, ctx: CanvasCtx, variant: str):
    """Tô / bát trên bàn."""
    is_night = variant == "night"
    cx   = ctx.x(0.38)
    ty   = ctx.ground_top + ctx.r(0.005)
    th   = ctx.r(0.060)
    tleg = ctx.r(0.040)
    bowl_y = ty + tleg + th - ctx.r(0.010)

    soup_colors = {
        "lunch":   "#FF6F00",
        "night":   "#BF360C",
        "weekend": "#F57F17",
    }
    soup_c = soup_colors.get(variant, "#FF6F00")

    for bx_off in [-ctx.r(0.040), ctx.r(0.040)]:
        bx = cx + bx_off
        br = ctx.r(0.026)

        # Thân tô
        bowl_rim = mpatches.Ellipse(
            (bx, bowl_y), br * 2.2, br * 0.70,
            color=BOWL_RIM, alpha=0.90, zorder=7
        )
        ax.add_patch(bowl_rim); patches.append(bowl_rim)

        # Nước súp
        soup = mpatches.Ellipse(
            (bx, bowl_y - ctx.r(0.004)), br * 1.70, br * 0.45,
            color=soup_c, alpha=0.80, zorder=8
        )
        ax.add_patch(soup); patches.append(soup)

        # Hơi bốc từ tô
        for pi in range(2):
            sx_off2 = ctx.r(np.random.uniform(-0.008, 0.008))
            steam_puff = plt.Circle(
                (bx + sx_off2, bowl_y + ctx.r(0.018 + pi * 0.020)),
                ctx.r(0.008 - pi * 0.002),
                color=STEAM_COLOR,
                alpha=0.30 - pi * 0.08, zorder=8
            )
            ax.add_patch(steam_puff); patches.append(steam_puff)

    # Đũa / muỗng
    ax.plot(
        [cx - ctx.r(0.068), cx - ctx.r(0.052)],
        [bowl_y + ctx.r(0.005), bowl_y + ctx.r(0.032)],
        '-', color="#8D6E63", lw=ctx.lw(0.010), zorder=8
    )
    ax.plot(
        [cx + ctx.r(0.055), cx + ctx.r(0.072)],
        [bowl_y + ctx.r(0.005), bowl_y + ctx.r(0.032)],
        '-', color="#8D6E63", lw=ctx.lw(0.010), zorder=8
    )


# ── Sidewalk plant ────────────────────────────────────────────────────────────

def _draw_sidewalk_plant(ax, patches, ctx: CanvasCtx,
                         nx: float, variant: str):
    """Chậu cây / cây nhỏ ven vỉa hè."""
    is_night = variant == "night"
    cx  = ctx.x(nx)
    py  = ctx.ground_top
    pot_h = ctx.r(0.060)
    pot_w = ctx.r(0.050)

    # Chậu
    pot = FancyBboxPatch(
        (cx - pot_w / 2, py), pot_w, pot_h,
        boxstyle="round,pad=0.004",
        facecolor="#795548" if not is_night else "#3E2723",
        edgecolor="#5D4037",
        linewidth=ctx.lw(0.010), zorder=5
    )
    ax.add_patch(pot); patches.append(pot)

    # Tán lá
    leaf_c = "#2E7D32" if not is_night else "#1B5E20"
    leaf_top = py + pot_h
    for lx, ly, lr in [
        (cx,           leaf_top + ctx.r(0.055), ctx.r(0.040)),
        (cx - ctx.r(0.030), leaf_top + ctx.r(0.030), ctx.r(0.026)),
        (cx + ctx.r(0.028), leaf_top + ctx.r(0.028), ctx.r(0.024)),
    ]:
        leaf = plt.Circle(
            (lx, ly), lr,
            color=leaf_c, alpha=0.90, zorder=6
        )
        ax.add_patch(leaf); patches.append(leaf)


# ── String lights ─────────────────────────────────────────────────────────────

def _draw_string_lights(ax, patches, ctx: CanvasCtx, variant: str):
    """Dây đèn trang trí — đặc trưng quán ăn đêm / cuối tuần VN."""
    is_night   = variant == "night"
    is_weekend = variant == "weekend"

    if not (is_night or is_weekend):
        return   # ban trưa không cần đèn trang trí

    bulb_c = LAMP_BULB
    glow_c = LAMP_GLOW_N if is_night else LAMP_GLOW_L

    # Dây đèn vắt ngang từ cột trái sang cột phải
    y_cord = ctx.zone_y("mid", 0.68)
    n_bulbs = 8
    x_start = ctx.x(0.06)
    x_end   = ctx.x(0.94)

    cord = ax.plot(
        [x_start, x_end], [y_cord, y_cord],
        '-', color=LAMP_CORD,
        lw=ctx.lw(0.008), alpha=0.60, zorder=6
    )[0]
    patches.append(cord)

    for i in range(n_bulbs):
        bx = x_start + (x_end - x_start) * i / (n_bulbs - 1)
        # Dây nhỏ thòng xuống
        drop_len = ctx.r(0.022)
        drop = ax.plot(
            [bx, bx], [y_cord, y_cord - drop_len],
            '-', color=LAMP_CORD,
            lw=ctx.lw(0.007), alpha=0.55, zorder=6
        )[0]
        patches.append(drop)

        # Bóng đèn tròn
        bulb = plt.Circle(
            (bx, y_cord - drop_len - ctx.r(0.012)),
            ctx.r(0.012),
            color=bulb_c, alpha=0.95, zorder=7
        )
        ax.add_patch(bulb); patches.append(bulb)

        if is_night:
            glow = plt.Circle(
                (bx, y_cord - drop_len - ctx.r(0.012)),
                ctx.r(0.030),
                color=glow_c, alpha=0.18, zorder=6
            )
            ax.add_patch(glow); patches.append(glow)



def animate_background_street_food(ax, ctx, variant: str, t_sec: float) -> list:
    """
    Dynamic elements quán ăn vỉa hè:
    - Diềm bạt lay theo gió (tất cả)
    - Khói nồi wiggle (lunch / night)
    - Đèn dây nhấp nháy (night / weekend)
    - Bảng hiệu glow pulse (night)
    """
    arts = []
    is_night = variant == "night"
    is_lunch = variant == "lunch"
    tarp_c   = "#F57F17" if is_night else ("#E53935" if is_lunch else "#1565C0")

    # ── Diềm bạt lay theo gió ─────────────────────────────────────────────────
    tarp_left  = ctx.x(0.01)
    tarp_right = ctx.x(0.99)
    fringe_y   = ctx.zone_y("mid", 0.72) - ctx.r(0.06) - ctx.r(0.008)
    fringe_h   = ctx.r(0.028)
    fw         = (tarp_right - tarp_left) / 10
    for fi in range(10):
        fx   = tarp_left + (tarp_right - tarp_left) * fi / 10
        sway = math.sin(t_sec * 2.0 + fi * 0.4) * ctx.r(0.008)
        fringe = mpatches.Polygon(
            [(fx,          fringe_y + sway),
             (fx + fw,     fringe_y + sway),
             (fx + fw / 2, fringe_y - fringe_h + sway * 1.5)],
            color=tarp_c, alpha=0.75, zorder=6
        )
        ax.add_patch(fringe)
        arts.append(fringe)

    # ── Khói nồi wiggle (lunch / night) ──────────────────────────────────────
    if variant in ("lunch", "night"):
        base_y  = ctx.ground_top + ctx.r(0.10) + ctx.r(0.052) * 0.80
        smoke_c = "#90A4AE" if is_night else "#CFD8DC"
        for i in range(4):
            sx   = ctx.x(0.74) + math.sin(t_sec * 2.5 + i * 0.9) * ctx.r(0.018)
            sy   = base_y + i * ctx.r(0.055)
            puff = plt.Circle((sx, sy), ctx.r(0.020 + i * 0.008),
                              color=smoke_c, alpha=max(0.04, 0.36 - i * 0.08), zorder=7)
            ax.add_patch(puff)
            arts.append(puff)

    # ── Đèn dây nhấp nháy (night / weekend) ──────────────────────────────────
    if variant in ("night", "weekend"):
        y_cord  = ctx.zone_y("mid", 0.68)
        x_start = ctx.x(0.06)
        x_end   = ctx.x(0.94)
        glow_c  = "#FF8F00" if is_night else "#FFD54F"
        for i in range(8):
            bx      = x_start + (x_end - x_start) * i / 7
            bulb_cy = y_cord - ctx.r(0.022) - ctx.r(0.012)
            flicker = 0.14 + math.sin(t_sec * 3.0 + i * 0.7) * 0.06
            glow    = plt.Circle((bx, bulb_cy), ctx.r(0.032),
                                 color=glow_c, alpha=flicker, zorder=6)
            ax.add_patch(glow)
            arts.append(glow)

    # ── Bảng hiệu glow pulse (night) ─────────────────────────────────────────
    if is_night:
        sign_alpha = 0.10 + math.sin(t_sec * 2.2) * 0.04
        sign_glow  = plt.Circle(
            (ctx.x(0.50), ctx.zone_y("mid", 0.76) + ctx.r(0.075) / 2),
            ctx.r(0.16), color="#FF6F00", alpha=sign_alpha, zorder=6
        )
        ax.add_patch(sign_glow)
        arts.append(sign_glow)

    return arts