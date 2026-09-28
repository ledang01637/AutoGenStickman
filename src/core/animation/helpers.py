# src/core/animation/helpers.py
"""
helpers.py — FK / IK solvers cho tay và chân.

Ba hàm private, chỉ dùng nội bộ trong poses/*.py:
  _arm()     → FK tay: góc vào, tọa độ ra
  _arm_ik()  → IK tay: tọa độ target vào, tọa độ elbow ra
  _leg()     → FK chân: góc vào, tọa độ ra

Không chứa logic animation (không dùng t, không dùng sin/cos dao động).
Không chứa hằng số — toàn bộ import từ constants.py.

Toán học sử dụng:
  FK  → Polar-to-Cartesian: x = origin_x + L × sin(θ), y = origin_y - L × cos(θ)
  IK  → Law of Cosines + atan2: tìm góc từ 3 cạnh đã biết, chọn 1 trong 2 nghiệm
"""

import math

from .constants import (
    LEN_ARM, LEN_FOREARM,
    LEN_THIGH, LEN_CALF,
    _X_R,
)


# ══════════════════════════════════════════════════════════════════════════════
# FK Tay
# ══════════════════════════════════════════════════════════════════════════════

def _arm(sh_x: float, sh_y: float,
         ang_s: float, ang_e: float,
         side: int) -> tuple[tuple, tuple]:
    """
    FK tay từ shoulder → elbow → hand.

    Áp dụng Polar-to-Cartesian hai lần liên tiếp:
      Lần 1: shoulder → elbow  (dùng ang_s)
      Lần 2: elbow   → hand    (dùng ang_s + ang_e, vì forearm xoay tương đối)

    Tham số:
      sh_x, sh_y  : tọa độ shoulder (điểm gốc của cánh tay)
      ang_s       : góc xoay cánh tay trên tính từ trục dọc (radian)
                    0   = tay thẳng xuống
                    +   = tay về phía trước
                    -   = tay về phía sau
      ang_e       : góc gập khuỷu tương đối so với cánh tay trên (radian)
                    0   = duỗi thẳng
                    +   = gập khuỷu
      side        : +1 = tay phải, -1 = tay trái
                    nhân với _X_R để tạo offset ngang vai

    Trả về:
      (ex, ey) : tọa độ elbow
      (hx, hy) : tọa độ hand
    """
    # Shoulder → Elbow
    ex = sh_x + _X_R * side + LEN_ARM * math.sin(ang_s)
    ey = sh_y               - LEN_ARM * math.cos(ang_s)
    #          ↑ dấu trừ: y tăng xuống dưới trong matplotlib coord system
    #            cos(0)=1 → khi ang_s=0, elbow thẳng dưới shoulder đúng 1 LEN_ARM

    # Elbow → Hand (ang_s + ang_e vì forearm xoay tương đối theo cánh tay trên)
    hx = ex + LEN_FOREARM * math.sin(ang_s + ang_e)
    hy = ey - LEN_FOREARM * math.cos(ang_s + ang_e)

    return (ex, ey), (hx, hy)


# ══════════════════════════════════════════════════════════════════════════════
# IK Tay
# ══════════════════════════════════════════════════════════════════════════════

def _arm_ik(sh_x: float, sh_y: float,
            hx: float, hy: float,
            side: int,
            prefer_elbow_up: bool = False) -> tuple[tuple, tuple]:
    """
    IK 2D tay — tính elbow từ vị trí target của hand.

    Bài toán ngược của _arm(): biết shoulder và hand, tìm elbow.

    Quy trình:
      1. Tính vai thật (real_sh) — lệch ra ngoài 0.16 so với tâm torso
      2. Tính vector và khoảng cách d từ vai thật đến target hand
      3. Clamp d để tránh acos nhận giá trị ngoài [-1, 1] → NaN
      4. Law of Cosines → alpha (góc tại shoulder trong tam giác S-E-H)
      5. atan2 → theta (hướng đường thẳng shoulder → hand)
      6. ea1 = theta + alpha, ea2 = theta - alpha → 2 nghiệm elbow
      7. Chọn nghiệm theo prefer_elbow_up (Elbow Gravity Rule)

    Tham số:
      sh_x, sh_y      : tọa độ shoulder (tâm torso, chưa offset)
      hx, hy          : tọa độ target hand (IK target từ constants.py)
      side            : +1 = tay phải, -1 = tay trái
      prefer_elbow_up : False (default) → khuỷu thấp — ăn/uống bình thường
                        True            → khuỷu cao  — chugging, ném, giơ tay

    Trả về:
      (ex, ey) : tọa độ elbow (tính ngược từ target)
      (hx, hy) : tọa độ hand  (chính là target, pass-through)
    """
    # Bước 1 — Vai thật trong front-view
    # sh_x là tâm torso; vai thật lệch ra 0.16 theo side
    # -0.02 vì vai thật cao hơn điểm nối torso một chút
    real_sh_x = sh_x + 0.16 * side
    real_sh_y = sh_y - 0.02

    # Bước 2 — Vector từ vai thật đến target hand
    dx = hx - real_sh_x
    dy = hy - real_sh_y

    # Bước 3 — Clamp khoảng cách
    # Nếu target xa hơn tổng chiều dài 2 xương, acos → domain error → NaN → crash
    # -0.001 giữ tay trong tầm với, duỗi gần thẳng thay vì báo lỗi
    d = math.hypot(dx, dy)
    d = min(d, LEN_ARM + LEN_FOREARM - 0.001)

    # Bước 4 — Law of Cosines: tìm alpha (góc tại shoulder)
    # Tam giác S-E-H: cạnh SE = LEN_ARM, cạnh EH = LEN_FOREARM, cạnh SH = d
    # cos(alpha) = (SE² + SH² - EH²) / (2 × SE × SH)
    cos_a = (LEN_ARM**2 + d**2 - LEN_FOREARM**2) / (2 * LEN_ARM * d)
    cos_a = max(-1.0, min(1.0, cos_a))   # clamp phòng floating point error
    alpha  = math.acos(cos_a)

    # Bước 5 — atan2: hướng đường thẳng shoulder → hand
    theta = math.atan2(dy, dx)

    # Bước 6 — Hai nghiệm elbow
    # ea1 và ea2 đối xứng qua đường thẳng shoulder → hand
    ea1 = theta + alpha
    ea2 = theta - alpha
    ey1 = real_sh_y + LEN_ARM * math.sin(ea1)   # y của elbow theo nghiệm 1
    ey2 = real_sh_y + LEN_ARM * math.sin(ea2)   # y của elbow theo nghiệm 2

    # Bước 7 — Chọn nghiệm theo Elbow Gravity Rule
    # ey nhỏ hơn = khuỷu thấp hơn (trong matplotlib: y nhỏ = lên trên)
    if prefer_elbow_up:
        ea = ea1 if ey1 > ey2 else ea2   # chọn nghiệm có ey cao hơn (lớn hơn)
    else:
        ea = ea1 if ey1 < ey2 else ea2   # chọn nghiệm có ey thấp hơn (nhỏ hơn)

    # Tính tọa độ elbow từ nghiệm đã chọn
    ex = real_sh_x + LEN_ARM * math.cos(ea)
    ey = real_sh_y + LEN_ARM * math.sin(ea)

    return (ex, ey), (hx, hy)


# ══════════════════════════════════════════════════════════════════════════════
# FK Chân
# ══════════════════════════════════════════════════════════════════════════════

def _leg(hip_x: float, hip_y: float,
         ang_h: float, ang_k: float,
         side: int) -> tuple[tuple, tuple]:
    """
    FK chân từ hip → knee → foot.

    Cấu trúc giống _arm(): Polar-to-Cartesian hai lần.
    Khác biệt: ang_k phải luôn âm hoặc bằng 0 (Knee Constraint).

    Knee Constraint — gối chỉ gập về sau, không bao giờ gập về trước:
      ang_k = -WALK_KNEE_AMP * max(0, -cos(w - 0.4))
      max(0, ...) cắt bỏ phần dương → ang_k ≤ 0 mọi lúc
      Hàm này không tự enforce — caller (pose_*) chịu trách nhiệm truyền đúng.

    Tham số:
      hip_x, hip_y : tọa độ hip — gốc tọa độ (0, 0) trong hầu hết các pose
      ang_h        : góc xoay đùi tính từ trục dọc (radian)
                     0   = chân thẳng xuống
                     +   = chân về phía trước
                     -   = chân về phía sau
      ang_k        : góc gập gối tương đối so với đùi (radian, phải ≤ 0)
                     0   = gối duỗi thẳng
                     -   = gối gập về sau (đúng giải phẫu)
      side         : +1 = chân phải, -1 = chân trái

    Trả về:
      (kx, ky) : tọa độ knee
      (fx, fy) : tọa độ foot
    """
    # Hip → Knee
    kx = hip_x + _X_R * side + LEN_THIGH * math.sin(ang_h)
    ky = hip_y               - LEN_THIGH * math.cos(ang_h)

    # Knee → Foot (ang_h + ang_k vì ống chân xoay tương đối theo đùi)
    fx = kx + LEN_CALF * math.sin(ang_h + ang_k)
    fy = ky - LEN_CALF * math.cos(ang_h + ang_k)

    return (kx, ky), (fx, fy)


