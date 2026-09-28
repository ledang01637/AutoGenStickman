"""
props.py — Prop drawing functions

Mỗi prop là 1 hàm vẽ lên ax tại vị trí (x, y).
Tọa độ (x, y) = điểm neo (anchor point) của prop,
thường là r_hand hoặc l_hand của stickman.

Convention:
  - Tất cả hàm nhận (ax, x, y, scale=1.0, z=10) → list[artist]
  - scale nhân theo CHAR_SCALE của stickman để prop tự động
    to/nhỏ tương ứng nhân vật
  - Trả về list artists để renderer có thể clear

Props có sẵn (18):
  Đồ ăn/uống  : bowl, cup, boba, bag_food
  Đồ dùng     : phone, laptop, book, document
  Tiền/tài chính : wallet, money_bag, coin, price_tag
  Cảm xúc/hiệu ứng : broken_heart, fire, trophy, dumbbell
  Công việc   : briefcase, clock

Dùng:
  from .props import PROP_FN, draw_prop
  arts = draw_prop(ax, "bowl", x=4.5, y=2.3, scale=1.1)
"""

from matplotlib.axes import Axes
from matplotlib.artist import Artist
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, Arc

# ── Type alias ────────────────────────────────────────────────────────────────
from typing import Callable

PropFn = Callable[[Axes, float, float, float, int], list[Artist]]


# ── Đồ ăn / uống ─────────────────────────────────────────────────────────────

def prop_bowl(ax, x, y, scale=1.0, z=10):
    """Tô phở / bún — tay cầm hoặc đặt trên bàn."""
    arts = []
    s = scale * 0.18
    body = FancyBboxPatch(
        (x - s, y - s * 0.44), s * 2, s * 1.10,
        boxstyle="round,pad=0.015",
        facecolor="#F5F0E8", edgecolor="#00000025",
        linewidth=0.5 * scale, zorder=z,
    )
    ax.add_patch(body); arts.append(body)

    food = mpatches.Ellipse(
        (x, y + s * 0.55), s * 1.55, s * 0.50,
        facecolor="#C0622A", edgecolor="none", zorder=z + 0.1,
    )
    ax.add_patch(food); arts.append(food)

    # Hơi bốc
    for sxi in [x - s * 0.28, x + s * 0.30]:
        sv  = np.linspace(y + s * 0.78, y + s * 1.55, 10)
        sxv = sxi + s * 0.11 * np.sin(np.linspace(0, 2 * np.pi, 10))
        l = ax.plot(sxv, sv, color="#E8E0D8", lw=1.0 * scale,
                    alpha=0.60, zorder=z + 0.2)[0]
        arts.append(l)
    return arts


def prop_cup(ax, x, y, scale=1.0, z=10):
    """Ly cà phê / trà — tay cầm."""
    arts = []
    s = scale * 0.14
    body = FancyBboxPatch(
        (x - s * 0.72, y - s * 0.50), s * 1.44, s * 1.80,
        boxstyle="round,pad=0.010",
        facecolor="#795548", edgecolor="#4E342E",
        linewidth=0.6 * scale, zorder=z,
    )
    ax.add_patch(body); arts.append(body)

    # Nắp
    lid = mpatches.Ellipse(
        (x, y + s * 1.30), s * 1.55, s * 0.40,
        facecolor="#5D4037", edgecolor="none", zorder=z + 0.1,
    )
    ax.add_patch(lid); arts.append(lid)

    # Hơi bốc
    sv  = np.linspace(y + s * 1.50, y + s * 2.30, 10)
    sxv = x + s * 0.15 * np.sin(np.linspace(0, 2 * np.pi, 10))
    l = ax.plot(sxv, sv, color="#E0D0C8", lw=0.9 * scale,
                alpha=0.55, zorder=z + 0.2)[0]
    arts.append(l)
    return arts


def prop_boba(ax, x, y, scale=1.0, z=10):
    """Trà sữa trân châu — icon viral."""
    arts = []
    s = scale * 0.14
    # Cốc
    body = FancyBboxPatch(
        (x - s * 0.80, y - s * 0.60), s * 1.60, s * 2.00,
        boxstyle="round,pad=0.010",
        facecolor="#FFE0B2", edgecolor="#FF8F00",
        linewidth=0.7 * scale, zorder=z,
    )
    ax.add_patch(body); arts.append(body)

    # Trân châu
    rng = np.random.RandomState(7)
    for _ in range(5):
        bx = x + rng.uniform(-s * 0.45, s * 0.45)
        by = y + rng.uniform(-s * 0.40, s * 0.10)
        bb = mpatches.Circle(
            (bx, by), s * 0.20,
            facecolor="#4E342E", edgecolor="none", zorder=z + 0.1,
        )
        ax.add_patch(bb); arts.append(bb)

    # Ống hút
    straw = ax.plot(
        [x + s * 0.30, x + s * 0.50],
        [y - s * 0.30, y + s * 2.20],
        "-", color="#E53935", lw=1.8 * scale, zorder=z + 0.2,
    )[0]
    arts.append(straw)
    return arts


def prop_bag_food(ax, x, y, scale=1.0, z=10):
    """Túi đồ ăn mang về."""
    arts = []
    s = scale * 0.16
    body = FancyBboxPatch(
        (x - s, y - s * 1.25), s * 2.0, s * 2.0,
        boxstyle="round,pad=0.015",
        facecolor="#FFECB3", edgecolor="#FF8F00",
        linewidth=0.6 * scale, zorder=z,
    )
    ax.add_patch(body); arts.append(body)

    # Quai xách
    l = ax.plot(
        [x - s * 0.55, x - s * 0.55, x + s * 0.55, x + s * 0.55],
        [y + s * 0.75, y + s * 1.15, y + s * 1.15, y + s * 0.75],
        "-", color="#FF8F00", lw=1.4 * scale, zorder=z + 0.1,
    )[0]
    arts.append(l)

    # Chữ nhỏ
    ax.text(x, y - s * 0.35, "ĂN", ha="center", va="center",
            fontsize=5.5 * scale, fontweight="bold",
            color="#E65100", zorder=z + 0.2)
    return arts


# ── Đồ dùng cá nhân ──────────────────────────────────────────────────────────

def prop_phone(ax, x, y, scale=1.0, z=10):
    """Điện thoại — viral content, mạng xã hội."""
    arts = []
    s = scale * 0.09
    body = FancyBboxPatch(
        (x - s, y - s * 2.00), s * 2.0, s * 3.30,
        boxstyle="round,pad=0.012",
        facecolor="#263238", edgecolor="#546E7A",
        linewidth=0.6 * scale, zorder=z,
    )
    ax.add_patch(body); arts.append(body)

    screen = mpatches.Rectangle(
        (x - s * 0.75, y - s * 1.75), s * 1.50, s * 2.80,
        facecolor="#B3E5FC", edgecolor="none", zorder=z + 0.1,
    )
    ax.add_patch(screen); arts.append(screen)

    # Notification dot
    notif = mpatches.Circle(
        (x + s * 0.55, y + s * 1.10), s * 0.28,
        facecolor="#F44336", edgecolor="none", zorder=z + 0.2,
    )
    ax.add_patch(notif); arts.append(notif)
    return arts


def prop_laptop(ax, x, y, scale=1.0, z=10):
    """Laptop — work from home, deadline."""
    arts = []
    s = scale * 0.20
    # Màn hình
    screen_body = FancyBboxPatch(
        (x - s, y), s * 2.0, s * 1.30,
        boxstyle="round,pad=0.012",
        facecolor="#263238", edgecolor="#37474F",
        linewidth=0.7 * scale, zorder=z,
    )
    ax.add_patch(screen_body); arts.append(screen_body)

    screen = mpatches.Rectangle(
        (x - s * 0.88, y + s * 0.10), s * 1.76, s * 1.10,
        facecolor="#4FC3F7", edgecolor="none", zorder=z + 0.1,
    )
    ax.add_patch(screen); arts.append(screen)

    # Bàn phím
    keyboard = FancyBboxPatch(
        (x - s * 1.10, y - s * 0.22), s * 2.20, s * 0.24,
        boxstyle="round,pad=0.006",
        facecolor="#37474F", edgecolor="#263238",
        linewidth=0.5 * scale, zorder=z,
    )
    ax.add_patch(keyboard); arts.append(keyboard)
    return arts


def prop_book(ax, x, y, scale=1.0, z=10):
    """Sách — học hành, đọc sách."""
    arts = []
    s = scale * 0.14
    body = FancyBboxPatch(
        (x - s * 0.65, y - s * 0.90), s * 1.30, s * 1.80,
        boxstyle="round,pad=0.008",
        facecolor="#1565C0", edgecolor="#0D47A1",
        linewidth=0.6 * scale, zorder=z,
    )
    ax.add_patch(body); arts.append(body)

    # Gáy sách
    spine = mpatches.Rectangle(
        (x - s * 0.65, y - s * 0.90), s * 0.12, s * 1.80,
        facecolor="#0D47A1", edgecolor="none", zorder=z + 0.1,
    )
    ax.add_patch(spine); arts.append(spine)

    # Dòng chữ giả
    for dy in [-0.30, -0.05, 0.20]:
        ax.plot(
            [x - s * 0.42, x + s * 0.50],
            [y + s * dy, y + s * dy],
            "-", color="#FFFFFF", lw=0.8 * scale, alpha=0.50, zorder=z + 0.2,
        )
    return arts


def prop_document(ax, x, y, scale=1.0, z=10):
    """Giấy tờ / hóa đơn / văn bản."""
    arts = []
    s = scale * 0.14
    body = FancyBboxPatch(
        (x - s * 0.75, y - s * 0.90), s * 1.50, s * 1.80,
        boxstyle="round,pad=0.006",
        facecolor="#FAFAFA", edgecolor="#B0BEC5",
        linewidth=0.5 * scale, zorder=z,
    )
    ax.add_patch(body); arts.append(body)

    for dy in [-0.50, -0.20, 0.10, 0.40, 0.70]:
        w = 1.0 if dy != 0.70 else 0.55
        ax.plot(
            [x - s * 0.55, x - s * 0.55 + s * 1.10 * w],
            [y + s * dy, y + s * dy],
            "-", color="#90A4AE", lw=0.9 * scale, zorder=z + 0.1,
        )
    return arts


# ── Tiền / tài chính ─────────────────────────────────────────────────────────

def prop_wallet(ax, x, y, scale=1.0, z=10):
    """Ví tiền (còn tiền)."""
    arts = []
    s = scale * 0.14
    body = FancyBboxPatch(
        (x - s, y - s * 0.55), s * 2.0, s * 1.10,
        boxstyle="round,pad=0.012",
        facecolor="#795548", edgecolor="#4E342E",
        linewidth=0.7 * scale, zorder=z,
    )
    ax.add_patch(body); arts.append(body)

    # Tiền nhô ra
    bill = FancyBboxPatch(
        (x - s * 0.60, y + s * 0.42), s * 1.20, s * 0.40,
        boxstyle="round,pad=0.004",
        facecolor="#A5D6A7", edgecolor="#388E3C",
        linewidth=0.4 * scale, zorder=z + 0.1,
    )
    ax.add_patch(bill); arts.append(bill)
    return arts


def prop_money_bag(ax, x, y, scale=1.0, z=10):
    """Túi tiền — icon viral tài chính."""
    arts = []
    s = scale * 0.16
    # Túi
    bag = mpatches.Circle(
        (x, y), s,
        facecolor="#FFD54F", edgecolor="#FF8F00",
        linewidth=0.8 * scale, zorder=z,
    )
    ax.add_patch(bag); arts.append(bag)

    # Cổ túi
    neck = FancyBboxPatch(
        (x - s * 0.28, y + s * 0.80), s * 0.56, s * 0.38,
        boxstyle="round,pad=0.005",
        facecolor="#FF8F00", edgecolor="none", zorder=z + 0.1,
    )
    ax.add_patch(neck); arts.append(neck)

    # Ký hiệu $
    ax.text(x, y - s * 0.05, "$", ha="center", va="center",
            fontsize=9 * scale, fontweight="bold",
            color="#E65100", zorder=z + 0.2)
    return arts


def prop_coin(ax, x, y, scale=1.0, z=10):
    """Đồng xu — nhỏ gọn."""
    arts = []
    s = scale * 0.10
    coin = mpatches.Circle(
        (x, y), s,
        facecolor="#FFD54F", edgecolor="#FF8F00",
        linewidth=0.7 * scale, zorder=z,
    )
    ax.add_patch(coin); arts.append(coin)
    ax.text(x, y, "₫", ha="center", va="center",
            fontsize=7 * scale, fontweight="bold",
            color="#E65100", zorder=z + 0.1)
    return arts


def prop_price_tag(ax, x, y, scale=1.0, z=10):
    """Thẻ giá — mua sắm, khuyến mãi."""
    arts = []
    s = scale * 0.14
    tag = FancyBboxPatch(
        (x - s, y - s * 0.60), s * 2.0, s * 1.20,
        boxstyle="round,pad=0.010",
        facecolor="#E53935", edgecolor="#B71C1C",
        linewidth=0.6 * scale, zorder=z,
    )
    ax.add_patch(tag); arts.append(tag)

    hole = mpatches.Circle(
        (x - s * 0.72, y + s * 0.20), s * 0.16,
        facecolor="white", edgecolor="none", zorder=z + 0.1,
    )
    ax.add_patch(hole); arts.append(hole)

    ax.text(x + s * 0.06, y - s * 0.02, "SALE", ha="center", va="center",
            fontsize=5.5 * scale, fontweight="bold",
            color="white", zorder=z + 0.2)
    return arts


# ── Cảm xúc / hiệu ứng ───────────────────────────────────────────────────────

def prop_broken_heart(ax, x, y, scale=1.0, z=10):
    """Tim vỡ — chia tay, thất tình."""
    arts = []
    s = scale * 0.15
    for side, sx in [("left", -s * 0.12), ("right", s * 0.12)]:
        heart_half = mpatches.Circle(
            (x + sx, y + s * 0.28), s * 0.42,
            facecolor="#E53935", edgecolor="none", zorder=z,
        )
        ax.add_patch(heart_half); arts.append(heart_half)

    # Đỉnh nhọn
    tip = mpatches.Polygon(
        [(x - s * 0.55, y + s * 0.18), (x + s * 0.55, y + s * 0.18),
         (x, y - s * 0.55)],
        facecolor="#E53935", edgecolor="none", zorder=z,
    )
    ax.add_patch(tip); arts.append(tip)

    # Vết nứt
    crack = ax.plot(
        [x, x - s * 0.15, x + s * 0.08, x],
        [y + s * 0.60, y + s * 0.20, y - s * 0.15, y - s * 0.55],
        "-", color="white", lw=1.4 * scale, zorder=z + 0.1,
    )[0]
    arts.append(crack)
    return arts


def prop_fire(ax, x, y, scale=1.0, z=10):
    """Lửa — deadline cháy, hot trend."""
    arts = []
    s = scale * 0.15
    colors = ["#FF6D00", "#FF9800", "#FFD54F"]
    for i, (col, hs) in enumerate(zip(colors, [1.0, 0.75, 0.50])):
        flame = mpatches.Ellipse(
            (x + (i - 1) * s * 0.22, y + s * 0.55 * hs * 0.5),
            s * 0.50 * hs, s * 1.10 * hs,
            facecolor=col, edgecolor="none",
            alpha=0.90, zorder=z + i * 0.1,
        )
        ax.add_patch(flame); arts.append(flame)
    return arts


def prop_trophy(ax, x, y, scale=1.0, z=10):
    """Cúp vàng — chiến thắng, thành công."""
    arts = []
    s = scale * 0.14
    # Cốc
    cup = FancyBboxPatch(
        (x - s * 0.72, y - s * 0.10), s * 1.44, s * 1.20,
        boxstyle="round,pad=0.015",
        facecolor="#FFD54F", edgecolor="#FF8F00",
        linewidth=0.7 * scale, zorder=z,
    )
    ax.add_patch(cup); arts.append(cup)

    # Tay cầm 2 bên
    for sx in [-s * 0.72, s * 0.72]:
        handle = Arc(
            (x + sx * 0.62, y + s * 0.50), s * 0.55, s * 0.60,
            angle=0,
            theta1=270 if sx < 0 else 90,
            theta2=90  if sx < 0 else 270,
            color="#FF8F00", linewidth=1.6 * scale, zorder=z + 0.1,
        )
        ax.add_patch(handle); arts.append(handle)

    # Chân đế
    base = FancyBboxPatch(
        (x - s * 0.55, y - s * 0.38), s * 1.10, s * 0.28,
        boxstyle="round,pad=0.006",
        facecolor="#FF8F00", edgecolor="none", zorder=z,
    )
    ax.add_patch(base); arts.append(base)

    # Sao
    ax.text(x, y + s * 0.52, "★", ha="center", va="center",
            fontsize=7 * scale, color="#FF6F00", zorder=z + 0.2)
    return arts


def prop_dumbbell(ax, x, y, scale=1.0, z=10):
    """Tạ tập gym."""
    arts = []
    s = scale * 0.14
    # Thanh giữa
    bar = ax.plot(
        [x - s * 1.10, x + s * 1.10], [y, y],
        "-", color="#546E7A", lw=2.5 * scale, zorder=z,
    )[0]
    arts.append(bar)

    for sx in [-s * 0.90, s * 0.90]:
        weight = mpatches.Ellipse(
            (x + sx, y), s * 0.36, s * 0.70,
            facecolor="#37474F", edgecolor="#263238",
            linewidth=0.6 * scale, zorder=z + 0.1,
        )
        ax.add_patch(weight); arts.append(weight)
    return arts


# ── Công việc ─────────────────────────────────────────────────────────────────

def prop_briefcase(ax, x, y, scale=1.0, z=10):
    """Cặp công sở."""
    arts = []
    s = scale * 0.16
    body = FancyBboxPatch(
        (x - s, y - s * 0.70), s * 2.0, s * 1.40,
        boxstyle="round,pad=0.012",
        facecolor="#5D4037", edgecolor="#3E2723",
        linewidth=0.7 * scale, zorder=z,
    )
    ax.add_patch(body); arts.append(body)

    handle = Arc(
        (x, y + s * 0.70), s * 0.90, s * 0.44,
        angle=0, theta1=0, theta2=180,
        color="#3E2723", linewidth=1.8 * scale, zorder=z + 0.1,
    )
    ax.add_patch(handle); arts.append(handle)

    # Khóa
    lock = mpatches.Rectangle(
        (x - s * 0.12, y - s * 0.08), s * 0.24, s * 0.22,
        facecolor="#8D6E63", edgecolor="none", zorder=z + 0.1,
    )
    ax.add_patch(lock); arts.append(lock)
    return arts


def prop_clock(ax, x, y, scale=1.0, z=10):
    """Đồng hồ — deadline, trễ giờ."""
    arts = []
    s = scale * 0.13
    face = mpatches.Circle(
        (x, y), s,
        facecolor="#ECEFF1", edgecolor="#455A64",
        linewidth=1.0 * scale, zorder=z,
    )
    ax.add_patch(face); arts.append(face)

    # Kim giờ (chỉ 12h) — tượng trưng deadline
    hh = ax.plot(
        [x, x - s * 0.28], [y, y + s * 0.50],
        "-", color="#263238", lw=1.8 * scale, zorder=z + 0.1,
    )[0]
    arts.append(hh)
    mh = ax.plot(
        [x, x + s * 0.48], [y, y + s * 0.20],
        "-", color="#263238", lw=1.4 * scale, zorder=z + 0.1,
    )[0]
    arts.append(mh)
    return arts


# ── Registry ──────────────────────────────────────────────────────────────────

PROP_FN: dict[str, PropFn] = {
    # Đồ ăn / uống
    "bowl":       prop_bowl,
    "cup":        prop_cup,
    "boba":       prop_boba,
    "bag_food":   prop_bag_food,
    # Đồ dùng cá nhân
    "phone":      prop_phone,
    "laptop":     prop_laptop,
    "book":       prop_book,
    "document":   prop_document,
    # Tiền / tài chính
    "wallet":     prop_wallet,
    "money_bag":  prop_money_bag,
    "coin":       prop_coin,
    "price_tag":  prop_price_tag,
    # Cảm xúc / hiệu ứng
    "broken_heart": prop_broken_heart,
    "fire":         prop_fire,
    "trophy":       prop_trophy,
    "dumbbell":     prop_dumbbell,
    # Công việc
    "briefcase":  prop_briefcase,
    "clock":      prop_clock,
}

PROP_NAMES = list(PROP_FN.keys())


def draw_prop(ax, name: str, x: float, y: float,
              scale: float = 1.0, z: int = 10) -> list:
    """
    Vẽ prop theo tên tại vị trí (x, y).
    Trả về list artists. Trả về [] nếu tên không hợp lệ.
    """
    fn = PROP_FN.get(name)
    if fn is None:
        return []
    return fn(ax, x, y, scale=scale, z=z)