"""
patch_animate.py — Tự động append animate_background_XXX vào đúng file.

Chạy từ root project:
    python patch_animate.py

Idempotent: kiểm tra function đã tồn tại chưa trước khi append.
"""

import os

BG_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Nội dung append cho từng file ────────────────────────────────────────────

PATCHES = {

"office.py": '''
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
''',

"park_day.py": '''
import math


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
''',

"gym.py": '''
import math


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
''',

"cafe.py": '''
import math


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
''',

"bedroom.py": '''
import math


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
''',

"city_day.py": '''
import math


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
''',

"street_food.py": '''
import math


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
''',

}

# ── Chạy patch ────────────────────────────────────────────────────────────────
def patch_file(filename: str, code: str) -> None:
    path = os.path.join(BG_DIR, filename)
    if not os.path.exists(path):
        print(f"  SKIP — không tìm thấy: {path}")
        return

    content = open(path, encoding="utf-8").read()
    fn_name = f"def animate_background_{filename.replace('.py', '')}("
    if fn_name in content:
        print(f"  SKIP — {filename} đã có animate function rồi")
        return

    snippet = code.lstrip("\n")

    # Xử lý từng import thiếu ở top file
    needed_imports = ["import math", "import numpy as np",
                      "import matplotlib.pyplot as plt",
                      "import matplotlib.patches as mpatches"]

    lines = content.splitlines()
    missing = [imp for imp in needed_imports
               if not any(l.strip() == imp for l in lines)]

    if missing:
        insert_at = 0
        for i, line in enumerate(lines):
            if line.startswith("import ") or line.startswith("from "):
                insert_at = i + 1
        for imp in reversed(missing):
            lines.insert(insert_at, imp)
        content = "\n".join(lines)
        # Xóa các dòng import trùng trong snippet
        snippet_lines = snippet.splitlines()
        snippet = "\n".join(l for l in snippet_lines
                            if l.strip() not in needed_imports)

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n\n" + snippet)
    print(f"  OK  — {filename}")

if __name__ == "__main__":
    print(f"BG_DIR: {BG_DIR}\n")
    for filename, code in PATCHES.items():
        patch_file(filename, code)
    print("\nDone.")