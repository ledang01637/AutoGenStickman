"""
Canvas coordinate system cho animation backgrounds.

Mọi background dùng CanvasCtx để convert tọa độ normalized (0→1)
sang tọa độ thực của canvas, giúp scale sang mọi tỉ lệ mà không
cần sửa code background.

Cách dùng:
    ctx = CanvasCtx("9:16")
    build_background_office(ax, ctx, variant="day")

    ctx = CanvasCtx("16:9")
    build_background_office(ax, ctx, variant="day")  # tự scale
"""

# ── Canvas presets ─────────────────────────────────────────────────────────────
CANVAS_PRESETS = {
    "9:16": {"w": 9,  "h": 16, "platform": "tiktok/reels"},
    "16:9": {"w": 16, "h": 9,  "platform": "youtube"},
    "1:1":  {"w": 9,  "h": 9,  "platform": "instagram"},
}

# ── Layout zones ───────────────────────────────────────────────────────────────
# Mỗi zone = (y_normalized_bot, y_normalized_top)
# 0.0 = đáy canvas, 1.0 = đỉnh canvas
#
# Lý do zones khác nhau theo ratio:
#   9:16 (dọc)  — nhiều không gian dọc → trời chiếm nhiều hơn
#   16:9 (ngang) — canvas thấp → phải nén lại, ground rộng hơn
#   1:1 (vuông) — trung gian
LAYOUT_ZONES = {
    "9:16": {
        "sky":    (0.68, 1.00),   # 32% — bầu trời, mây, mặt trời/trăng
        "mid":    (0.19, 0.68),   # 49% — tòa nhà, cây, objects
        "ground": (0.00, 0.19),   # 19% — đường, sàn, vỉa hè
    },
    "16:9": {
        "sky":    (0.55, 1.00),   # 45%
        "mid":    (0.22, 0.55),   # 33%
        "ground": (0.00, 0.22),   # 22%
    },
    "1:1": {
        "sky":    (0.62, 1.00),   # 38%
        "mid":    (0.18, 0.62),   # 44%
        "ground": (0.00, 0.18),   # 18%
    },
}

# ── Stickman pose geometry (từ poses.py) ──────────────────────────────────────
_POSE_FOOT_DY  = 0.92   # l_foot dy tối đa (âm) — chân thấp nhất
_POSE_HEAD_DY  = 1.08   # head dy — đỉnh đầu

# ── Stickman scale theo ratio ──────────────────────────────────────────────────
# Nhân vật cần lớn hơn trên canvas ngang vì chiều cao ít hơn
CHAR_SCALE = {
    "9:16": 0.10,   # 10% của min(W,H)
    "16:9": 0.13,
    "1:1":  0.11,
}

# ── Stroke width scale ─────────────────────────────────────────────────────────
# Đường kẻ cần mỏng hơn trên canvas lớn hơn
STROKE_BASE = {
    "9:16": 1.0,
    "16:9": 0.85,
    "1:1":  0.95,
}


class CanvasCtx:
    """
    Context object truyền vào mọi hàm vẽ background.

    Tất cả tọa độ viết trong không gian normalized 0→1,
    gọi .x() .y() .r() để convert ra canvas thực.

    Ví dụ:
        ctx = CanvasCtx("9:16")

        # Tọa độ
        ctx.x(0.5)          # → 4.5  (giữa canvas ngang)
        ctx.y(0.5)          # → 8.0  (giữa canvas dọc)

        # Radius — không méo khi canvas không vuông
        ctx.r(0.05)         # → 0.45 (5% của min(9,16)=9)

        # Zone helpers
        ctx.zone_y("sky", 0.5)      # y giữa vùng trời
        ctx.fill_zone("ground")     # (x,y,w,h) toàn bộ vùng đất
    """

    def __init__(self, ratio: str = "9:16"):
        if ratio not in CANVAS_PRESETS:
            raise ValueError(
                f"ratio '{ratio}' không hợp lệ. "
                f"Chọn một trong: {list(CANVAS_PRESETS.keys())}"
            )
        preset     = CANVAS_PRESETS[ratio]
        self.W     = preset["w"]
        self.H     = preset["h"]
        self.ratio = ratio
        self.platform = preset["platform"]

        # Zone boundaries (tọa độ thực, tính sẵn để dùng nhanh)
        z = LAYOUT_ZONES[ratio]
        self.sky_bot    = z["sky"][0]    * self.H
        self.sky_top    = z["sky"][1]    * self.H
        self.mid_bot    = z["mid"][0]    * self.H
        self.mid_top    = z["mid"][1]    * self.H
        self.ground_bot = 0.0
        self.ground_top = z["ground"][1] * self.H

        # Stickman defaults
        self.char_scale = self.r(CHAR_SCALE[ratio])
        self.char_y     = self.ground_top + self.char_scale * _POSE_FOOT_DY

        # Stroke scale — dùng cho linewidth
        self._stroke_base = STROKE_BASE[ratio]

    # ── Coordinate converters ──────────────────────────────────────────────────

    def x(self, v: float) -> float:
        """Normalized x (0→1) → tọa độ x thực."""
        return v * self.W

    def y(self, v: float) -> float:
        """Normalized y (0→1) → tọa độ y thực."""
        return v * self.H

    def r(self, v: float) -> float:
        """
        Normalized radius/scalar (0→1) → giá trị thực.
        Scale theo min(W, H) để hình tròn không bị méo
        khi canvas không vuông.
        """
        return v * min(self.W, self.H)

    def lw(self, v: float) -> float:
        """
        Normalized line width → giá trị thực.
        Tự điều chỉnh theo ratio để đường kẻ trông đều trên mọi canvas.
        """
        return v * min(self.W, self.H) * self._stroke_base

    # ── Zone helpers ───────────────────────────────────────────────────────────

    def zone_y(self, zone: str, frac: float) -> float:
        """
        Tọa độ y thực tại vị trí frac trong zone.

        Args:
            zone: "sky" | "mid" | "ground"
            frac: 0.0 = đáy zone, 1.0 = đỉnh zone

        Ví dụ:
            ctx.zone_y("sky", 0.0)   # = ctx.sky_bot
            ctx.zone_y("sky", 1.0)   # = ctx.sky_top
            ctx.zone_y("mid", 0.5)   # giữa zone mid
        """
        z = LAYOUT_ZONES[self.ratio][zone]
        return (z[0] + frac * (z[1] - z[0])) * self.H

    def zone_h(self, zone: str) -> float:
        """Chiều cao tuyệt đối của zone."""
        z = LAYOUT_ZONES[self.ratio][zone]
        return (z[1] - z[0]) * self.H

    def fill_zone(self, zone: str,
                  frac_bot: float = 0.0,
                  frac_top: float = 1.0) -> tuple:
        """
        Trả về (x, y, w, h) để vẽ Rectangle lấp đầy zone.

        Args:
            zone: "sky" | "mid" | "ground"
            frac_bot: 0.0 = đáy zone
            frac_top: 1.0 = đỉnh zone

        Ví dụ:
            ax.add_patch(Rectangle(*ctx.fill_zone("sky"), color="blue"))
            ax.add_patch(Rectangle(*ctx.fill_zone("mid", 0.5, 1.0), ...))
        """
        z  = LAYOUT_ZONES[self.ratio][zone]
        y0 = (z[0] + frac_bot * (z[1] - z[0])) * self.H
        y1 = (z[0] + frac_top * (z[1] - z[0])) * self.H
        return (0, y0, self.W, y1 - y0)

    def full_width(self, y: float, h: float) -> tuple:
        """(0, y, W, h) — Rectangle full width tại y."""
        return (0, y, self.W, h)

    # ── Misc ──────────────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return (f"CanvasCtx(ratio={self.ratio!r}, "
                f"W={self.W}, H={self.H}, "
                f"platform={self.platform!r})")


# ── Convenience factory ────────────────────────────────────────────────────────

def make_ctx(ratio: str = "9:16") -> CanvasCtx:
    """Shorthand tạo CanvasCtx."""
    return CanvasCtx(ratio)


def all_ratios() -> list[str]:
    """Trả về list tất cả ratios có sẵn."""
    return list(CANVAS_PRESETS.keys())