"""
Shared drawing helpers cho tất cả background modules.

Tất cả hàm nhận CanvasCtx và dùng ctx.x/y/r để tọa độ
tự scale theo canvas ratio.

KHÔNG có draw_caption_area ở đây —
caption là UI layer, xử lý bởi renderer.py.
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from .canvas import CanvasCtx


# ── Axis setup ────────────────────────────────────────────────────────────────

def setup_ax(ax, ctx: CanvasCtx) -> None:
    """
    Thiết lập ax theo ctx. Gọi ở đầu mỗi build_background_*().

    Đặt xlim/ylim, tắt trục số, đảm bảo aspect ratio đúng.
    """
    ax.set_xlim(0, ctx.W)
    ax.set_ylim(0, ctx.H)
    ax.set_aspect('equal')
    ax.axis('off')


# ── Gradient ──────────────────────────────────────────────────────────────────

def gradient_rect(ax, patches: list,
                  col_top: str, col_bot: str,
                  y_bot: float, y_top: float,
                  x_start: float = 0,
                  width: float = None,
                  steps: int = 30,
                  zorder: int = 0) -> None:
    """
    Vẽ gradient từ col_bot (dưới) → col_top (trên)
    bằng cách xếp chồng nhiều Rectangle mỏng.

    Args:
        y_bot, y_top: tọa độ thực (đã qua ctx.y())
        width: mặc định = ctx.W (full width)
        steps: càng nhiều càng mượt, tốn thêm memory
    """
    if width is None:
        width = ax.get_xlim()[1]   # lấy từ ax để không cần truyền ctx

    h_step  = (y_top - y_bot) / steps
    r1, g1, b1 = _hex_to_rgb(col_bot)
    r2, g2, b2 = _hex_to_rgb(col_top)

    for i in range(steps):
        t  = i / steps
        rc = r1 + (r2 - r1) * t
        gc = g1 + (g2 - g1) * t
        bc = b1 + (b2 - b1) * t
        rect = mpatches.Rectangle(
            (x_start, y_bot + i * h_step),
            width, h_step + 0.02,   # +0.02 tránh gap giữa các strip
            color=(rc, gc, bc),
            zorder=zorder
        )
        ax.add_patch(rect)
        patches.append(rect)


def _hex_to_rgb(hex_color: str) -> tuple:
    """#RRGGBB → (r, g, b) trong [0,1]."""
    h = hex_color.lstrip('#')
    return tuple(int(h[i:i+2], 16) / 255 for i in (0, 2, 4))


# ── Sky ───────────────────────────────────────────────────────────────────────

def draw_sky(ax, patches: list, ctx: CanvasCtx,
             col_top: str, col_bot: str,
             steps: int = 30, zorder: int = 0) -> None:
    """Vẽ gradient trời từ sky_bot → sky_top."""
    gradient_rect(ax, patches, col_top, col_bot,
                  y_bot=ctx.sky_bot, y_top=ctx.sky_top,
                  width=ctx.W, steps=steps, zorder=zorder)


def draw_ground(ax, patches: list, ctx: CanvasCtx,
                color: str, zorder: int = 1) -> None:
    """Vẽ nền ground zone (solid color)."""
    x, y, w, h = ctx.fill_zone("ground")
    rect = mpatches.Rectangle(
        (x, y), w, h,
        color=color, zorder=zorder
    )
    ax.add_patch(rect)
    patches.append(rect)


def draw_floor_planks(ax, patches: list, ctx: CanvasCtx,
                      base_color: str, plank_color: str,
                      n_lines: int = 5, zorder: int = 2) -> None:
    """Vẽ vân sàn gỗ (đường ngang nhạt)."""
    y_bot = ctx.ground_bot
    y_top = ctx.ground_top
    for i in range(1, n_lines + 1):
        y = y_bot + (y_top - y_bot) * i / (n_lines + 1)
        l = ax.plot([0, ctx.W], [y, y], '-',
                    color=plank_color, lw=ctx.lw(0.008),
                    alpha=0.35, zorder=zorder)[0]
        patches.append(l)


# ── Sun / Moon ────────────────────────────────────────────────────────────────

def draw_sun(ax, patches: list, ctx: CanvasCtx,
             nx: float = 0.85, ny: float = 0.92,
             color: str = "#FFD54F",
             glow_color: str = "#FFE57F",
             zorder: int = 2) -> None:
    """
    Vẽ mặt trời + glow.
    nx, ny: vị trí normalized (0→1).
    """
    cx, cy = ctx.x(nx), ctx.y(ny)
    r = ctx.r(0.048)

    glow = plt.Circle((cx, cy), r * 1.55,
                       color=glow_color, alpha=0.22, zorder=zorder)
    ax.add_patch(glow); patches.append(glow)

    sun = plt.Circle((cx, cy), r,
                     color=color, alpha=0.92, zorder=zorder + 1)
    ax.add_patch(sun); patches.append(sun)


def draw_moon(ax, patches: list, ctx: CanvasCtx,
              nx: float = 0.80, ny: float = 0.92,
              zorder: int = 2) -> None:
    """Vẽ mặt trăng + glow."""
    cx, cy = ctx.x(nx), ctx.y(ny)
    r = ctx.r(0.038)

    glow = plt.Circle((cx, cy), r * 1.6,
                       color="#FFF9C4", alpha=0.18, zorder=zorder)
    ax.add_patch(glow); patches.append(glow)

    moon = plt.Circle((cx, cy), r,
                      color="#FFF9C4", alpha=0.92, zorder=zorder + 1)
    ax.add_patch(moon); patches.append(moon)


# ── Clouds ────────────────────────────────────────────────────────────────────

def draw_clouds(ax, patches: list, ctx: CanvasCtx,
                n: int = 4,
                y_frac_range: tuple = (0.2, 0.85),
                color: str = "white",
                alpha: float = 0.92,
                seed: int = 55,
                zorder: int = 3) -> None:
    """
    Vẽ n đám mây trong vùng sky.

    Args:
        y_frac_range: (frac_bot, frac_top) trong sky zone
    """
    rng = np.random.RandomState(seed)
    for _ in range(n):
        nx  = rng.uniform(0.05, 0.90)
        nfy = rng.uniform(*y_frac_range)
        nr  = rng.uniform(0.030, 0.055)

        cx = ctx.x(nx)
        cy = ctx.zone_y("sky", nfy)
        r  = ctx.r(nr)

        for dx, dy, dr in [
            (-0.55, 0,    0.40),
            (0,     0.14, 0.55),
            (0.55,  0,    0.40),
            (0.28, -0.08, 0.32),
            (-0.25,-0.05, 0.28),
        ]:
            cl = plt.Circle((cx + dx * r, cy + dy * r),
                             dr * r,
                             color=color, alpha=alpha, zorder=zorder)
            ax.add_patch(cl)
            patches.append(cl)


def draw_storm_clouds(ax, patches: list, ctx: CanvasCtx,
                      n: int = 5, seed: int = 21,
                      zorder: int = 3) -> None:
    """Mây xám nặng cho variant rain / night."""
    rng = np.random.RandomState(seed)
    for _ in range(n):
        nx  = rng.uniform(0.02, 0.88)
        nfy = rng.uniform(0.25, 0.90)
        nr  = rng.uniform(0.050, 0.090)

        cx = ctx.x(nx)
        cy = ctx.zone_y("sky", nfy)
        r  = ctx.r(nr)

        for dx, dy, dr in [
            (-0.5, 0, 0.50), (0, 0.12, 0.68),
            (0.5,  0, 0.50), (0.22,-0.09, 0.38),
        ]:
            cl = plt.Circle((cx + dx * r, cy + dy * r),
                             dr * r,
                             color="#607D8B", alpha=0.82, zorder=zorder)
            ax.add_patch(cl)
            patches.append(cl)


# ── Rain ──────────────────────────────────────────────────────────────────────

def draw_rain(ax, patches: list, ctx: CanvasCtx,
              n: int = 55, seed: int = 21,
              color: str = "#90CAF9",
              zorder: int = 9) -> None:
    """Vẽ giọt mưa nghiêng."""
    rng = np.random.RandomState(seed)
    for _ in range(n):
        nx = rng.uniform(0.02, 0.98)
        ny = rng.uniform(0.03, 0.97)
        nl = rng.uniform(0.012, 0.024)

        rx = ctx.x(nx)
        ry = ctx.y(ny)
        rl = ctx.r(nl)

        rain = ax.plot(
            [rx, rx - rl * 0.18],
            [ry, ry - rl],
            '-', color=color,
            lw=ctx.lw(0.008),
            alpha=rng.uniform(0.3, 0.6),
            zorder=zorder
        )[0]
        patches.append(rain)


# ── Stars ─────────────────────────────────────────────────────────────────────

def draw_stars(ax, patches: list, ctx: CanvasCtx,
               n: int = 20, seed: int = 7,
               zorder: int = 2) -> None:
    """Vẽ sao đêm trong vùng sky."""
    rng = np.random.RandomState(seed)
    for _ in range(n):
        nx  = rng.uniform(0.02, 0.98)
        nfy = rng.uniform(0.05, 0.95)
        sz  = rng.uniform(1.5, 3.8)
        alpha = rng.uniform(0.4, 0.9)

        sx = ctx.x(nx)
        sy = ctx.zone_y("sky", nfy)

        star = ax.plot([sx], [sy], '*',
                       color="#FFF9C4",
                       markersize=sz * ctx.r(0.012) / 0.1,
                       alpha=alpha, zorder=zorder)[0]
        patches.append(star)


# ── Trees ─────────────────────────────────────────────────────────────────────

def draw_tree(ax, patches: list, ctx: CanvasCtx,
              nx: float, y_base: float,
              trunk_color: str = "#5D4037",
              leaf_color: str = "#388E3C",
              scale: float = 1.0,
              zorder: int = 4) -> None:
    """
    Vẽ 1 cây đơn giản.

    Args:
        nx: vị trí x normalized (0→1)
        y_base: tọa độ y thực của gốc cây (ctx.ground_top thường)
        scale: nhân kích thước cây
    """
    cx   = ctx.x(nx)
    tw   = ctx.r(0.018) * scale   # trunk width
    th   = ctx.r(0.095) * scale   # trunk height
    lr   = ctx.r(0.055) * scale   # leaf radius base

    # Thân cây
    trunk = mpatches.Rectangle(
        (cx - tw / 2, y_base), tw, th,
        color=trunk_color, zorder=zorder
    )
    ax.add_patch(trunk); patches.append(trunk)

    # Tán lá — 5 vòng tròn lệch nhau
    leaf_top = y_base + th
    for lx, ly, ldr in [
        (cx,        leaf_top + lr * 0.90, 1.00),
        (cx - lr*0.65, leaf_top + lr * 0.55, 0.72),
        (cx + lr*0.65, leaf_top + lr * 0.50, 0.68),
        (cx - lr*0.30, leaf_top + lr * 1.30, 0.58),
        (cx + lr*0.28, leaf_top + lr * 1.25, 0.52),
    ]:
        lf = plt.Circle((lx, ly), lr * ldr,
                         color=leaf_color, alpha=0.92, zorder=zorder + 1)
        ax.add_patch(lf); patches.append(lf)


# ── Windows helper ────────────────────────────────────────────────────────────

def draw_window_grid(ax, patches: list, ctx: CanvasCtx,
                     bx: float, by: float, bw: float, bh: float,
                     win_color_fn,
                     col: int = None,
                     row: int = None,
                     zorder: int = 5) -> None:
    """
    Vẽ lưới cửa sổ trên mặt tòa nhà.

    Args:
        bx, by, bw, bh: bounding box tòa nhà (tọa độ thực)
        win_color_fn: callable() → màu cửa sổ (để caller control random)
        col, row: số cột/hàng cửa sổ (auto nếu None)
    """
    margin_x = bw * 0.12
    margin_y = bh * 0.08
    inner_w  = bw - 2 * margin_x
    inner_h  = bh - 2 * margin_y

    win_w  = ctx.r(0.032)
    win_h  = ctx.r(0.040)
    gap_x  = win_w * 1.6
    gap_y  = win_h * 1.6

    cols = col or max(1, int(inner_w / gap_x))
    rows = row or max(1, int(inner_h / gap_y))

    start_x = bx + margin_x + (inner_w - cols * gap_x + gap_x - win_w) / 2
    start_y = by + margin_y

    for ri in range(rows):
        for ci in range(cols):
            wx = start_x + ci * gap_x
            wy = start_y + ri * gap_y
            if wx + win_w > bx + bw - margin_x * 0.5:
                continue
            if wy + win_h > by + bh - margin_y * 0.5:
                continue
            wc = win_color_fn()
            win = mpatches.Rectangle(
                (wx, wy), win_w, win_h,
                color=wc, alpha=0.88, zorder=zorder
            )
            ax.add_patch(win)
            patches.append(win)


# ── Text helpers ──────────────────────────────────────────────────────────────

def draw_text_normalized(ax, patches: list, ctx: CanvasCtx,
                          nx: float, ny: float, text: str,
                          nsize: float = 0.040,
                          color: str = "#1a1a2e",
                          ha: str = "center",
                          va: str = "center",
                          fontweight: str = "normal",
                          zorder: int = 8) -> None:
    """
    Vẽ text tại vị trí normalized.

    nsize: font size normalized (ctx.r() scale)
    """
    t = ax.text(
        ctx.x(nx), ctx.y(ny), text,
        fontsize=ctx.r(nsize) * 10,  # *10 vì matplotlib dùng pt
        color=color,
        ha=ha, va=va,
        fontweight=fontweight,
        zorder=zorder
    )
    patches.append(t)
    return t