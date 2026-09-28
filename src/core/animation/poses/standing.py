"""
poses/standing.py — Các pose đứng yên: idle, talk, shrug.

Đặc điểm chung của standing poses:
  - Chân đứng thẳng: dùng **_STAND_LEGS, không gọi _leg()
  - Tất cả dùng breath cycle: sin(t * IDLE_BREATH_FREQ) * IDLE_BREATH_AMP
  - Upper body FK — tay tính từ góc, không có IK
  - Hip và shoulder dao động nhẹ theo breath, không có sway/bob locomotion

Breath cycle:
  breath = sin(t * 1.8) * 0.008
  → shoulder_y = TORSO_LEN + breath
  → head_y     = TORSO_LEN + HEAD_OFFSET + breath
  Biên độ 0.008 đủ thấy khi nhìn kỹ, không lộ liễu khi nhìn tổng thể.
"""

import math

from ..constants import (
    Keypoints,      
    TORSO_LEN, HEAD_OFFSET,
    IDLE_BREATH_FREQ, IDLE_BREATH_AMP,
    _STAND_LEGS,
)
from ..helpers import _arm


# ══════════════════════════════════════════════════════════════════════════════
# Idle
# ══════════════════════════════════════════════════════════════════════════════

def pose_idle(t: float = 0) -> "Keypoints":
    """
    Đứng yên thở — chỉ có breath cycle, không có chuyển động khác.

    Tay thả tự nhiên dọc theo thân:
      ang_s = 0.08  → tay hơi mở ra ngoài một chút (không chụm sát vào người)
      ang_e = 0.06  → khuỷu hơi gập nhẹ (tay thẳng hoàn toàn trông cứng nhắc)

    Đây là pose baseline — dùng làm trạng thái mặc định khi không có
    animation event nào được trigger từ JSON scene.
    """
    breath = math.sin(t * IDLE_BREATH_FREQ) * IDLE_BREATH_AMP
    sh     = (0.0, TORSO_LEN + breath)

    # Tay thả tự nhiên — góc nhỏ, đối xứng hai bên
    le, lh = _arm(*sh, ang_s= 0.08, ang_e=0.06, side=-1)
    re, rh = _arm(*sh, ang_s= 0.08, ang_e=0.06, side= 1)

    return dict(
        hip      = (0.0, 0.0),
        shoulder = sh,
        head     = (0.0, TORSO_LEN + HEAD_OFFSET + breath),
        l_elbow  = le, l_hand = lh,
        r_elbow  = re, r_hand = rh,
        **_STAND_LEGS,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Talk
# ══════════════════════════════════════════════════════════════════════════════

def pose_talk(t: float = 0) -> "Keypoints":
    """
    Đang nói chuyện — tay phải cử động nhẹ theo nhịp nói.

    Tay phải gesticulate: dao động lên xuống theo sin với tần số 2.5 Hz
      ang_s_r dao động từ -0.3 đến +0.1 → tay di chuyển trước-sau nhẹ
      ang_e_r dao động từ 0.3 đến 0.7   → khuỷu gập/duỗi theo nhịp

    Tay trái giữ nguyên idle — người nói chuyện thường chỉ dùng một tay.

    Breath cycle giữ nguyên — thở vẫn tiếp tục trong khi nói.
    """
    breath = math.sin(t * IDLE_BREATH_FREQ) * IDLE_BREATH_AMP
    sh     = (0.0, TORSO_LEN + breath)

    # Tay phải gesticulate theo nhịp nói
    talk_w  = t * 2.5
    ang_s_r = -0.2 + 0.15 * math.sin(talk_w)        # dao động trước-sau
    ang_e_r =  0.5 + 0.20 * math.sin(talk_w * 2.0)  # khuỷu gập theo nhịp

    # Tay trái idle
    le, lh = _arm(*sh, ang_s=0.08, ang_e=0.06, side=-1)
    re, rh = _arm(*sh, ang_s=ang_s_r, ang_e=ang_e_r, side=1)

    return dict(
        hip      = (0.0, 0.0),
        shoulder = sh,
        head     = (0.0, TORSO_LEN + HEAD_OFFSET + breath),
        l_elbow  = le, l_hand = lh,
        r_elbow  = re, r_hand = rh,
        **_STAND_LEGS,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Shrug
# ══════════════════════════════════════════════════════════════════════════════

def pose_shrug(t: float = 0) -> "Keypoints":
    """
    Nhún vai — hai tay giơ lên, lòng bàn tay hướng ra ngoài.

    Shrug có hai phase:
      Phase lên   (0.0 → 0.5s): vai nâng lên, tay giơ ra ngoài
      Phase giữ   (0.5 → 1.5s): giữ nguyên ở đỉnh
      Phase xuống (1.5 → 2.0s): trở về idle

    Dùng sin để tạo easing tự nhiên thay vì linear:
      shrug_t = clamp(sin(t * π / SHRUG_DURATION), 0, 1)

    Khi nhún vai:
      ang_s = -0.70 → tay giơ lên cao (góc âm = về phía trước/lên)
      ang_e =  0.60 → khuỷu gập, cẳng tay hướng ra ngoài
      shoulder_y tăng thêm shrug_lift → vai nhô lên
    """
    breath     = math.sin(t * IDLE_BREATH_FREQ) * IDLE_BREATH_AMP

    # Easing: sin làm mượt cả phase lên lẫn xuống
    SHRUG_DURATION = 2.0
    shrug_t  = abs(math.sin(t * math.pi / SHRUG_DURATION))
    shrug_t  = max(0.0, min(1.0, shrug_t))

    shrug_lift = shrug_t * 0.06    # vai nhô lên tối đa 0.06 units

    sh = (0.0, TORSO_LEN + breath + shrug_lift)

    # Góc tay interpolate từ idle đến shrug theo shrug_t
    ang_s = 0.08 + shrug_t * (-0.70 - 0.08)   # idle=0.08 → shrug=-0.70
    ang_e = 0.06 + shrug_t * ( 0.60 - 0.06)   # idle=0.06 → shrug=0.60

    le, lh = _arm(*sh, ang_s=ang_s, ang_e=ang_e, side=-1)
    re, rh = _arm(*sh, ang_s=ang_s, ang_e=ang_e, side= 1)

    return dict(
        hip      = (0.0, 0.0),
        shoulder = sh,
        head     = (0.0, TORSO_LEN + HEAD_OFFSET + breath + shrug_lift * 0.5),
        #                                                    ↑ đầu nhô lên 50% vai
        #                                                      giảm chấn, không cứng
        l_elbow  = le, l_hand = lh,
        r_elbow  = re, r_hand = rh,
        **_STAND_LEGS,
    )