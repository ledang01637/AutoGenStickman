"""
Background: Gym (Phòng tập thể dục)
Canvas: scale tự động qua CanvasCtx (9:16 / 16:9 / 1:1)

Phù hợp với chủ đề:
  - Bắt đầu hành trình tập gym, năm mới quyết tâm
  - Mệt mỏi sau buổi tập, muốn bỏ cuộc
  - Tập gym lúc sáng sớm, không có ai
  - Chen chúc giờ cao điểm, chờ máy mãi không được
  - Flex cơ bắp, khoe thành quả

Variants:
  morning  — sáng sớm vắng vẻ, ánh đèn huỳnh quang mát, yên tĩnh
  crowded  — giờ cao điểm, đèn sáng chói, năng lượng cao
  empty    — tối muộn / cuối tuần, đèn mờ, chỉ còn mình
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch

from .canvas import CanvasCtx
from .utils import setup_ax, gradient_rect
import math

# ── Palette ───────────────────────────────────────────────────────────────────
WALL_MORNING  = "#ECEFF1"
WALL_CROWDED  = "#F5F5F5"
WALL_EMPTY    = "#263238"

FLOOR_RUBBER  = "#37474F"
FLOOR_RUBBER2 = "#455A64"   # vân sàn cao su
FLOOR_MORNING = "#4CAF50"   # sàn xanh lá (morning)
FLOOR_MORN2   = "#388E3C"
FLOOR_CROWD   = "#37474F"
FLOOR_CROWD2  = "#455A64"

WALL_PAD_C    = "#1565C0"   # tấm đệm tường (xanh gym)
WALL_PAD_ALT  = "#0D47A1"
WALL_STRIPE   = "#1976D2"   # sọc trang trí

RACK_C        = "#546E7A"
RACK_DARK     = "#37474F"
BARBELL_C     = "#607D8B"
PLATE_COLORS  = ["#F44336", "#1565C0", "#4CAF50", "#FF8F00", "#9C27B0", "#37474F"]

BENCH_C       = "#212121"
BENCH_PAD     = "#1565C0"
DUMBBELL_C    = "#424242"
DUMBBELL_END  = "#616161"

MIRROR_C      = "#B3E5FC"
MIRROR_FRAME  = "#546E7A"
MIRROR_SHINE  = "#FFFFFF"

MACHINE_C     = "#37474F"
MACHINE_ACC   = "#546E7A"
MACHINE_PAD   = "#1A237E"
CABLE_C       = "#78909C"

LAMP_TUBE_C   = "#E3F2FD"   # đèn huỳnh quang
LAMP_HOUSING  = "#546E7A"
LAMP_GLOW_C   = "#E3F2FD"

MOTIVATE_BG   = "#B71C1C"   # nền poster động lực
CLOCK_C       = "#37474F"

SKIRTING_C    = "#263238"
CEILING_C     = "#CFD8DC"


def build_background_gym(ax, ctx: CanvasCtx, variant: str = "morning"):
    """
    Vẽ background phòng tập gym.

    Args:
        ax      : matplotlib Axes
        ctx     : CanvasCtx — xác định canvas ratio + helpers
        variant : "morning" | "crowded" | "empty"
    """
    patches = []
    setup_ax(ax, ctx)
    np.random.seed(42)

    is_morning = variant == "morning"
    is_crowded = variant == "crowded"
    is_empty   = variant == "empty"

    wall_c = (WALL_EMPTY   if is_empty
              else WALL_CROWDED if is_crowded
              else WALL_MORNING)

    # ── Trần ──────────────────────────────────────────────────────────────────
    ceiling_c = "#1A2327" if is_empty else CEILING_C
    ceiling = mpatches.Rectangle(
        (0, ctx.H - ctx.r(0.035)), ctx.W, ctx.r(0.035),
        color=ceiling_c, zorder=0
    )
    ax.add_patch(ceiling); patches.append(ceiling)

    # ── Tường ─────────────────────────────────────────────────────────────────
    wall = mpatches.Rectangle(
        (0, ctx.ground_top), ctx.W, ctx.H - ctx.ground_top - ctx.r(0.035),
        color=wall_c, zorder=0
    )
    ax.add_patch(wall); patches.append(wall)

    # Sọc trang trí tường (morning / crowded)
    if not is_empty:
        _draw_wall_stripes(ax, patches, ctx, variant=variant)

    # Tấm đệm tường dưới
    _draw_wall_pads(ax, patches, ctx, variant=variant)

    # Chân tường
    skirting = mpatches.Rectangle(
        (0, ctx.ground_top - ctx.r(0.010)),
        ctx.W, ctx.r(0.010),
        color=SKIRTING_C, zorder=2
    )
    ax.add_patch(skirting); patches.append(skirting)

    # ── Sàn cao su ────────────────────────────────────────────────────────────
    _draw_floor(ax, patches, ctx, variant=variant)

    # ── Gương lớn ─────────────────────────────────────────────────────────────
    _draw_mirrors(ax, patches, ctx, variant=variant)

    # ── Giá tạ (dumbbell rack) ────────────────────────────────────────────────
    _draw_dumbbell_rack(ax, patches, ctx, variant=variant)

    # ── Barbell + đĩa tạ ──────────────────────────────────────────────────────
    _draw_barbell_set(ax, patches, ctx, variant=variant)

    # ── Ghế tập (bench) ───────────────────────────────────────────────────────
    _draw_bench(ax, patches, ctx, variant=variant)

    # ── Máy tập (cable machine) ───────────────────────────────────────────────
    _draw_cable_machine(ax, patches, ctx, nx=0.88, variant=variant)

    # ── Đèn huỳnh quang trần ──────────────────────────────────────────────────
    _draw_ceiling_lights(ax, patches, ctx, variant=variant)

    # ── Poster động lực ───────────────────────────────────────────────────────
    _draw_motivation_poster(ax, patches, ctx, variant=variant)

    # ── Đồng hồ tường ─────────────────────────────────────────────────────────
    _draw_wall_clock(ax, patches, ctx, nx=0.50)

    # ── Overlay theo variant ──────────────────────────────────────────────────
    if is_empty:
        dark = mpatches.Rectangle(
            (0, 0), ctx.W, ctx.H,
            color="#0A0F12", alpha=0.42, zorder=8
        )
        ax.add_patch(dark); patches.append(dark)

    if is_crowded:
        # Ánh đèn chói overhead
        bright = mpatches.Rectangle(
            (0, 0), ctx.W, ctx.H,
            color="#FFFFFF", alpha=0.04, zorder=8
        )
        ax.add_patch(bright); patches.append(bright)

    return patches


# ── Helpers ───────────────────────────────────────────────────────────────────

def _draw_wall_stripes(ax, patches, ctx: CanvasCtx, variant: str):
    """Sọc màu trang trí tường — nét gym hiện đại."""
    stripe_c = "#1565C0" if variant == "morning" else "#E53935"
    stripe_alpha = 0.12 if variant == "morning" else 0.09

    # 2 sọc chéo lớn
    for i, (x_start, x_end) in enumerate([
        (ctx.x(0.05), ctx.x(0.35)),
        (ctx.x(0.60), ctx.x(0.90)),
    ]):
        y_bot = ctx.ground_top
        y_top = ctx.H - ctx.r(0.035)
        stripe = mpatches.Polygon(
            [
                (x_start,               y_bot),
                (x_start + ctx.r(0.10), y_bot),
                (x_end   + ctx.r(0.10), y_top),
                (x_end,                 y_top),
            ],
            color=stripe_c, alpha=stripe_alpha, zorder=1
        )
        ax.add_patch(stripe); patches.append(stripe)


def _draw_wall_pads(ax, patches, ctx: CanvasCtx, variant: str):
    """Tấm đệm bảo vệ tường phía dưới."""
    pad_h = ctx.zone_h("mid") * 0.20
    pad_y = ctx.ground_top

    pad_c   = "#1A2327" if variant == "empty" else WALL_PAD_C
    pad_alt = "#263238" if variant == "empty" else WALL_PAD_ALT

    n_pads = 7
    pad_w  = ctx.W / n_pads

    for i in range(n_pads):
        pc = pad_c if i % 2 == 0 else pad_alt
        pad = mpatches.Rectangle(
            (i * pad_w, pad_y), pad_w - ctx.r(0.004), pad_h,
            color=pc, alpha=0.70, zorder=2
        )
        ax.add_patch(pad); patches.append(pad)

        # Đường viền pad
        border = mpatches.Rectangle(
            (i * pad_w, pad_y), pad_w - ctx.r(0.004), pad_h,
            facecolor="none",
            edgecolor="#263238",
            linewidth=ctx.lw(0.008),
            alpha=0.40, zorder=3
        )
        ax.add_patch(border); patches.append(border)


def _draw_floor(ax, patches, ctx: CanvasCtx, variant: str):
    """Sàn cao su kẻ ô."""
    if variant == "morning":
        floor_c = FLOOR_MORNING
        floor_dk = FLOOR_MORN2
    elif variant == "crowded":
        floor_c = FLOOR_CROWD
        floor_dk = FLOOR_CROWD2
    else:
        floor_c = "#263238"
        floor_dk = "#1A2327"

    floor = mpatches.Rectangle(
        (0, 0), ctx.W, ctx.ground_top,
        color=floor_c, zorder=1
    )
    ax.add_patch(floor); patches.append(floor)

    # Vân sàn cao su — ô vuông nhỏ
    n_col = 10
    n_row = 4
    cw = ctx.W / n_col
    ch = ctx.ground_top / n_row
    for ri in range(n_row):
        for ci in range(n_col):
            if (ri + ci) % 2 == 0:
                tile = mpatches.Rectangle(
                    (ci * cw, ri * ch), cw, ch,
                    color=floor_dk, alpha=0.30, zorder=2
                )
                ax.add_patch(tile); patches.append(tile)

    # Đường kẻ ngang/dọc nhẹ
    for ci in range(1, n_col):
        vl = ax.plot(
            [ci * cw, ci * cw], [0, ctx.ground_top],
            '-', color=floor_dk,
            lw=ctx.lw(0.005), alpha=0.20, zorder=2
        )[0]
        patches.append(vl)
    for ri in range(1, n_row):
        hl = ax.plot(
            [0, ctx.W], [ri * ch, ri * ch],
            '-', color=floor_dk,
            lw=ctx.lw(0.005), alpha=0.20, zorder=2
        )[0]
        patches.append(hl)


def _draw_mirrors(ax, patches, ctx: CanvasCtx, variant: str):
    """Gương lớn chiếm toàn bộ nửa trái tường."""
    is_empty = variant == "empty"

    mw = ctx.W * 0.52
    mh = ctx.zone_h("mid") * 0.82
    mx = 0
    my = ctx.ground_top + ctx.zone_h("mid") * 0.14

    # Frame gương
    frame = mpatches.Rectangle(
        (mx - ctx.r(0.008), my - ctx.r(0.008)),
        mw + ctx.r(0.016), mh + ctx.r(0.016),
        color=MIRROR_FRAME, zorder=3
    )
    ax.add_patch(frame); patches.append(frame)

    # Mặt gương
    mirror_alpha = 0.10 if is_empty else 0.18
    mirror = mpatches.Rectangle(
        (mx, my), mw, mh,
        color=MIRROR_C, alpha=mirror_alpha, zorder=4
    )
    ax.add_patch(mirror); patches.append(mirror)

    # Phản chiếu — vệt sáng chéo
    for i, (xa, xb, alpha) in enumerate([
        (0.08, 0.16, 0.12),
        (0.28, 0.32, 0.08),
        (0.46, 0.50, 0.06),
    ]):
        shine = mpatches.Polygon(
            [
                (mx + mw * xa, my),
                (mx + mw * xb, my),
                (mx + mw * (xb - 0.04), my + mh),
                (mx + mw * (xa - 0.04), my + mh),
            ],
            color=MIRROR_SHINE,
            alpha=alpha * (0.5 if is_empty else 1.0),
            zorder=5
        )
        ax.add_patch(shine); patches.append(shine)

    # Đường chia gương (2 tấm)
    seam_x = mx + mw * 0.50
    seam = ax.plot(
        [seam_x, seam_x], [my, my + mh],
        '-', color=MIRROR_FRAME,
        lw=ctx.lw(0.012), zorder=5
    )[0]
    patches.append(seam)


def _draw_dumbbell_rack(ax, patches, ctx: CanvasCtx, variant: str):
    """Giá tạ tay + dumbbell."""
    is_empty = variant == "empty"

    rx = ctx.x(0.02)
    ry = ctx.ground_top + ctx.r(0.010)
    rw = ctx.W * 0.48
    rh = ctx.r(0.075)

    # Khung giá (3 tầng)
    for tier in range(3):
        tier_y = ry + tier * ctx.r(0.068)
        bar = mpatches.Rectangle(
            (rx, tier_y), rw, ctx.r(0.012),
            color=RACK_DARK, zorder=4
        )
        ax.add_patch(bar); patches.append(bar)

        # Thanh đứng giá
        for vx in [rx, rx + rw * 0.33, rx + rw * 0.66, rx + rw]:
            vbar = mpatches.Rectangle(
                (vx - ctx.r(0.006), ry),
                ctx.r(0.012), rh + ctx.r(0.070),
                color=RACK_C, zorder=3
            )
            ax.add_patch(vbar); patches.append(vbar)

    # Dumbbell trên giá — 3 cặp kích thước khác nhau
    np.random.seed(15)
    db_sizes  = [0.80, 0.92, 1.10]   # scale
    db_colors = [PLATE_COLORS[0], PLATE_COLORS[1], PLATE_COLORS[5]]

    for tier, (scale, dc) in enumerate(zip(db_sizes, db_colors)):
        tier_y = ry + tier * ctx.r(0.068) + ctx.r(0.014)
        # 3 cặp mỗi tầng
        for pair in range(3):
            db_cx = rx + rw * (0.10 + pair * 0.30)
            _draw_dumbbell(ax, patches, ctx,
                           cx=db_cx, cy=tier_y,
                           scale=scale, color=dc,
                           is_dark=is_empty)


def _draw_dumbbell(ax, patches, ctx: CanvasCtx,
                   cx: float, cy: float,
                   scale: float, color: str,
                   is_dark: bool = False):
    """1 cái tạ tay (dumbbell)."""
    bar_c  = "#1A1A1A" if is_dark else DUMBBELL_C
    end_c  = "#2A2A2A" if is_dark else color

    bar_w  = ctx.r(0.055) * scale
    bar_h  = ctx.r(0.012) * scale
    end_r  = ctx.r(0.018) * scale

    # Thanh giữa
    bar = mpatches.Rectangle(
        (cx - bar_w / 2, cy - bar_h / 2),
        bar_w, bar_h,
        color=bar_c, zorder=5
    )
    ax.add_patch(bar); patches.append(bar)

    # 2 đầu tạ
    for ex in [cx - bar_w / 2, cx + bar_w / 2]:
        end = plt.Circle(
            (ex, cy), end_r,
            color=end_c, zorder=6
        )
        ax.add_patch(end); patches.append(end)


def _draw_barbell_set(ax, patches, ctx: CanvasCtx, variant: str):
    """Barbell + đĩa tạ đặt dưới sàn."""
    is_empty   = variant == "empty"
    is_morning = variant == "morning"

    bx = ctx.x(0.30)
    by = ctx.ground_top * 0.28

    bar_len = ctx.r(0.55)
    bar_h   = ctx.r(0.010)

    # Thanh barbell
    bar = mpatches.Rectangle(
        (bx - bar_len / 2, by - bar_h / 2),
        bar_len, bar_h,
        color="#78909C" if not is_empty else "#546E7A",
        zorder=4
    )
    ax.add_patch(bar); patches.append(bar)

    # Đĩa tạ mỗi bên — 2-3 cái xếp chồng
    n_plates = 2 if is_morning else 3
    plate_configs = [
        (ctx.r(0.026), ctx.r(0.048), PLATE_COLORS[0]),   # lớn nhất, ngoài cùng
        (ctx.r(0.022), ctx.r(0.038), PLATE_COLORS[1]),
        (ctx.r(0.018), ctx.r(0.028), PLATE_COLORS[2]),
    ]

    for side in [-1, 1]:
        offset = ctx.r(0.010)
        for k in range(n_plates):
            pw, ph, pc = plate_configs[k]
            px = bx + side * (bar_len / 2 - offset - pw)
            plate = mpatches.Ellipse(
                (px + side * pw / 2, by),
                pw, ph,
                color=pc if not is_empty else "#37474F",
                alpha=0.90, zorder=5
            )
            ax.add_patch(plate); patches.append(plate)

            # Lỗ giữa đĩa
            hole = plt.Circle(
                (px + side * pw / 2, by),
                ctx.r(0.006),
                color=BARBELL_C, zorder=6
            )
            ax.add_patch(hole); patches.append(hole)

            offset += pw * 0.60


def _draw_bench(ax, patches, ctx: CanvasCtx, variant: str):
    """Ghế tập (flat bench)."""
    is_empty = variant == "empty"
    bx = ctx.x(0.38)
    by = ctx.ground_top * 0.55

    bw = ctx.r(0.30)
    bh = ctx.r(0.028)

    # Chân bench (4 chân)
    leg_h = ctx.ground_top * 0.44
    for lx in [bx + bw * 0.08, bx + bw * 0.92]:
        leg = mpatches.Rectangle(
            (lx - ctx.r(0.008), by - leg_h),
            ctx.r(0.016), leg_h,
            color=BENCH_C, zorder=4
        )
        ax.add_patch(leg); patches.append(leg)

        # Chân ngang dưới
        foot = mpatches.Rectangle(
            (lx - ctx.r(0.022), by - leg_h),
            ctx.r(0.044), ctx.r(0.008),
            color=BENCH_C, zorder=4
        )
        ax.add_patch(foot); patches.append(foot)

    # Mặt ghế (pad)
    pad_c = "#0D47A1" if is_empty else BENCH_PAD
    pad = FancyBboxPatch(
        (bx, by), bw, bh,
        boxstyle="round,pad=0.005",
        color=pad_c, zorder=5
    )
    ax.add_patch(pad); patches.append(pad)

    # Đường chỉ may trên pad
    stitch = ax.plot(
        [bx + ctx.r(0.010), bx + bw - ctx.r(0.010)],
        [by + bh * 0.50, by + bh * 0.50],
        '--', color="#1565C0",
        lw=ctx.lw(0.006), alpha=0.40, zorder=6
    )[0]
    patches.append(stitch)


def _draw_cable_machine(ax, patches, ctx: CanvasCtx,
                         nx: float, variant: str):
    """Máy tập cable / weight stack."""
    is_empty = variant == "empty"
    cx = ctx.x(nx)
    by = ctx.ground_top

    mw = ctx.r(0.14)
    mh = ctx.zone_h("mid") * 0.75

    # Khung máy
    frame = FancyBboxPatch(
        (cx - mw / 2, by), mw, mh,
        boxstyle="round,pad=0.006",
        color=MACHINE_C if not is_empty else "#1A2327",
        zorder=4
    )
    ax.add_patch(frame); patches.append(frame)

    # Weight stack (tạ xếp chồng)
    stack_w = mw * 0.55
    stack_h = mh * 0.60
    stack_x = cx - stack_w / 2
    stack_y = by + mh * 0.08

    for i in range(8):
        plate_h = stack_h / 8 - ctx.r(0.003)
        plate_y = stack_y + i * (stack_h / 8)
        plate_c = MACHINE_ACC if not is_empty else "#263238"
        alpha   = 1.0 - i * 0.04

        plate = mpatches.Rectangle(
            (stack_x, plate_y), stack_w, plate_h,
            color=plate_c, alpha=alpha, zorder=5
        )
        ax.add_patch(plate); patches.append(plate)

        # Pin selector
        if i == 3:
            pin = plt.Circle(
                (stack_x + stack_w + ctx.r(0.008), plate_y + plate_h / 2),
                ctx.r(0.006),
                color="#FF5722", zorder=7
            )
            ax.add_patch(pin); patches.append(pin)

    # Pulley trên cùng
    pulley_y = by + mh - ctx.r(0.018)
    pulley = plt.Circle(
        (cx, pulley_y), ctx.r(0.016),
        facecolor=MACHINE_ACC,
        edgecolor=RACK_DARK,
        linewidth=ctx.lw(0.010),
        zorder=6
    )
    ax.add_patch(pulley); patches.append(pulley)

    # Dây cáp
    cable = ax.plot(
        [cx, cx],
        [pulley_y - ctx.r(0.016), by + mh * 0.68],
        '-', color=CABLE_C,
        lw=ctx.lw(0.008), zorder=6
    )[0]
    patches.append(cable)

    # Handle
    handle_y = by + mh * 0.68
    handle = FancyBboxPatch(
        (cx - ctx.r(0.022), handle_y - ctx.r(0.014)),
        ctx.r(0.044), ctx.r(0.018),
        boxstyle="round,pad=0.004",
        color=RACK_DARK, zorder=7
    )
    ax.add_patch(handle); patches.append(handle)

    # Logo strip trang trí
    logo = mpatches.Rectangle(
        (cx - mw / 2, by + mh * 0.88),
        mw, ctx.r(0.012),
        color=WALL_PAD_C if not is_empty else "#1A237E",
        zorder=6
    )
    ax.add_patch(logo); patches.append(logo)


def _draw_ceiling_lights(ax, patches, ctx: CanvasCtx, variant: str):
    """Đèn huỳnh quang / LED panel trên trần."""
    is_empty   = variant == "empty"
    is_crowded = variant == "crowded"

    ceiling_y = ctx.H - ctx.r(0.035)
    n_lights  = 4
    positions = [ctx.x(0.15 + i * 0.23) for i in range(n_lights)]

    for lx in positions:
        tube_w = ctx.r(0.14)
        tube_h = ctx.r(0.014)

        # Housing
        housing = FancyBboxPatch(
            (lx - tube_w / 2 - ctx.r(0.008), ceiling_y - tube_h - ctx.r(0.008)),
            tube_w + ctx.r(0.016), tube_h + ctx.r(0.016),
            boxstyle="round,pad=0.003",
            color=LAMP_HOUSING, zorder=7
        )
        ax.add_patch(housing); patches.append(housing)

        # Tube
        tube_c = "#4A6070" if is_empty else LAMP_TUBE_C
        tube = mpatches.Rectangle(
            (lx - tube_w / 2, ceiling_y - tube_h),
            tube_w, tube_h,
            color=tube_c, alpha=0.90, zorder=8
        )
        ax.add_patch(tube); patches.append(tube)

        # Glow
        if not is_empty:
            glow_alpha = 0.12 if is_crowded else 0.08
            glow_h = ctx.zone_h("sky") * 0.55
            glow = mpatches.Polygon(
                [
                    (lx - tube_w / 2,          ceiling_y - tube_h),
                    (lx + tube_w / 2,          ceiling_y - tube_h),
                    (lx + tube_w / 2 + ctx.r(0.06), ceiling_y - tube_h - glow_h),
                    (lx - tube_w / 2 - ctx.r(0.06), ceiling_y - tube_h - glow_h),
                ],
                color=LAMP_GLOW_C, alpha=glow_alpha, zorder=6
            )
            ax.add_patch(glow); patches.append(glow)
        else:
            # Emergency light đỏ mờ khi empty
            emerg = plt.Circle(
                (lx, ceiling_y - tube_h / 2),
                ctx.r(0.008),
                color="#FF1744", alpha=0.60, zorder=9
            )
            ax.add_patch(emerg); patches.append(emerg)


def _draw_motivation_poster(ax, patches, ctx: CanvasCtx, variant: str):
    """Poster động lực treo tường."""
    is_empty = variant == "empty"

    pw = ctx.r(0.20)
    ph = ctx.r(0.14)
    px = ctx.x(0.50) - pw / 2
    py = ctx.zone_y("mid", 0.68)

    # Khung
    frame = FancyBboxPatch(
        (px - ctx.r(0.006), py - ctx.r(0.006)),
        pw + ctx.r(0.012), ph + ctx.r(0.012),
        boxstyle="round,pad=0.004",
        color=RACK_DARK, zorder=4
    )
    ax.add_patch(frame); patches.append(frame)

    # Nền poster
    bg_c = "#1A1A1A" if is_empty else MOTIVATE_BG
    poster = mpatches.Rectangle(
        (px, py), pw, ph,
        color=bg_c, zorder=5
    )
    ax.add_patch(poster); patches.append(poster)

    # Sọc chéo trang trí
    stripe = mpatches.Polygon(
        [
            (px,          py),
            (px + pw * 0.38, py),
            (px + pw * 0.22, py + ph),
            (px,          py + ph),
        ],
        color="#FFFFFF", alpha=0.06, zorder=6
    )
    ax.add_patch(stripe); patches.append(stripe)

    # Chữ giả (3 bar)
    bar_c = "#FFFFFF" if is_empty else "#FFD54F"
    for i, (bw_frac, by_frac) in enumerate([
        (0.65, 0.72), (0.50, 0.46), (0.38, 0.20)
    ]):
        bar = mpatches.Rectangle(
            (px + pw * (1 - bw_frac) / 2, py + ph * by_frac),
            pw * bw_frac, ctx.r(0.011),
            color=bar_c, alpha=0.85, zorder=6
        )
        ax.add_patch(bar); patches.append(bar)


def _draw_wall_clock(ax, patches, ctx: CanvasCtx, nx: float):
    """Đồng hồ tường."""
    cx = ctx.x(nx)
    cy = ctx.zone_y("mid", 0.88)
    r  = ctx.r(0.038)

    # Viền
    outer = plt.Circle(
        (cx, cy), r,
        facecolor=CLOCK_C,
        edgecolor="#1A2327",
        linewidth=ctx.lw(0.014),
        zorder=6
    )
    ax.add_patch(outer); patches.append(outer)

    # Mặt
    face = plt.Circle(
        (cx, cy), r * 0.82,
        facecolor="#ECEFF1", zorder=7
    )
    ax.add_patch(face); patches.append(face)

    # Kim giờ + phút
    for angle, length, lw_n in [
        (120, r * 0.42, 0.016),   # kim giờ
        (60,  r * 0.60, 0.012),   # kim phút
    ]:
        rad = np.deg2rad(angle)
        hand = ax.plot(
            [cx, cx + length * np.cos(rad)],
            [cy, cy + length * np.sin(rad)],
            '-', color=CLOCK_C,
            lw=ctx.lw(lw_n), zorder=8
        )[0]
        patches.append(hand)

    # Tâm
    center = plt.Circle(
        (cx, cy), ctx.r(0.006),
        color=CLOCK_C, zorder=9
    )
    ax.add_patch(center); patches.append(center)



def animate_background_gym(ax, ctx, variant: str, t_sec: float) -> list:
    """
    Dynamic elements gym:
    - Kim giây đồng hồ tường
    - Đèn ceiling pulse (morning / crowded)
    - Emergency light nhấp nháy đỏ (empty)
    - Gương: vệt sáng quét chậm
    """
    arts = []

    # ── Kim giây đồng hồ (nx=0.50) ───────────────────────────────────────────
    cx_clock  = ctx.x(0.50)
    cy_clock  = ctx.zone_y("mid", 0.88)
    r_clock   = ctx.r(0.038)
    sec_angle = math.radians(90 - (t_sec % 60) * 6)
    sx = cx_clock + r_clock * 0.72 * math.cos(sec_angle)
    sy = cy_clock + r_clock * 0.72 * math.sin(sec_angle)
    arts.append(ax.plot([cx_clock, sx], [cy_clock, sy],
                        "-", color="#E53935", lw=ctx.lw(0.009), zorder=10)[0])

    # ── Đèn ceiling pulse (morning / crowded) ─────────────────────────────────
    if variant in ("morning", "crowded"):
        ceiling_y  = ctx.H - ctx.r(0.035)
        tube_h     = ctx.r(0.014)
        glow_alpha = (0.10 if variant == "morning" else 0.14) + math.sin(t_sec * 0.7) * 0.02
        glow_h     = ctx.zone_h("sky") * 0.55
        for lx in [ctx.x(0.15 + i * 0.23) for i in range(4)]:
            tube_w = ctx.r(0.14)
            glow = mpatches.Polygon(
                [(lx - tube_w / 2,              ceiling_y - tube_h),
                 (lx + tube_w / 2,              ceiling_y - tube_h),
                 (lx + tube_w / 2 + ctx.r(0.06), ceiling_y - tube_h - glow_h),
                 (lx - tube_w / 2 - ctx.r(0.06), ceiling_y - tube_h - glow_h)],
                color="#E3F2FD", alpha=glow_alpha, zorder=6
            )
            ax.add_patch(glow)
            arts.append(glow)

    # ── Emergency light nhấp nháy đỏ (empty) ─────────────────────────────────
    if variant == "empty":
        blink     = (math.sin(t_sec * math.pi) + 1) / 2
        ceiling_y = ctx.H - ctx.r(0.035)
        tube_h    = ctx.r(0.014)
        for lx in [ctx.x(0.15 + i * 0.23) for i in range(4)]:
            emerg = plt.Circle((lx, ceiling_y - tube_h / 2), ctx.r(0.008),
                               color="#FF1744", alpha=0.35 + blink * 0.45, zorder=9)
            ax.add_patch(emerg)
            arts.append(emerg)

    # ── Gương: vệt sáng quét chậm (morning / crowded) ────────────────────────
    if variant != "empty":
        mw    = ctx.W * 0.52
        mh    = ctx.zone_h("mid") * 0.82
        my    = ctx.ground_top + ctx.zone_h("mid") * 0.14
        sweep = (t_sec % 4.0) / 4.0
        scx   = mw * sweep
        sw    = mw * 0.06
        shine = mpatches.Polygon(
            [(scx,        my),
             (scx + sw,   my),
             (scx + sw - ctx.r(0.02), my + mh),
             (scx - ctx.r(0.02),      my + mh)],
            color="#FFFFFF", alpha=0.07, zorder=5
        )
        ax.add_patch(shine)
        arts.append(shine)

    return arts