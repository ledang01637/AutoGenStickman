"""
poses/interaction.py — Các pose tương tác: drink, eat, hold.

Đặc điểm chung của interaction poses:
  - Tay phải dùng IK (_arm_ik): bàn tay lock vào target, khuỷu tự tính
  - Tay trái dùng FK (_arm): giữ tư thế idle hoặc hỗ trợ
  - Chân đứng thẳng: **_STAND_LEGS
  - Breath cycle giữ nguyên — cơ thể vẫn thở trong khi thực hiện hành động

Cross-body rule:
  Khi tay phải đưa vào miệng, target x nhỏ (gần trục 0).
  IK solver tự flare khuỷu ra ngoài để tránh chest clipping.
  Không cần xử lý thủ công — Law of Cosines tự giải quyết.

Elbow Gravity Rule:
  prefer_elbow_up=False (default) cho drink và eat — khuỷu chọn vị trí thấp.
  Ngoại lệ: nếu cần pose chugging (uống dốc ngược), truyền prefer_elbow_up=True.
"""

import math

from ..constants import (
    Keypoints,      
    TORSO_LEN, HEAD_OFFSET,
    IDLE_BREATH_FREQ, IDLE_BREATH_AMP,
    DRINK_HAND_X, DRINK_HAND_Y,
    EAT_HAND_X,   EAT_HAND_Y,
    HOLD_HAND_X,  HOLD_HAND_Y,
    _STAND_LEGS,
)
from ..helpers import _arm, _arm_ik


# ══════════════════════════════════════════════════════════════════════════════
# Drink
# ══════════════════════════════════════════════════════════════════════════════

def pose_drink(t: float = 0) -> "Keypoints":
    """
    Uống nước — tay phải IK lock vào miệng, tay trái giữ tự nhiên.

    IK target: (DRINK_HAND_X=0.08, DRINK_HAND_Y=1.15)
      x=0.08 → gần trục miệng, hơi sang phải
      y=1.15 → cao hơn shoulder (TORSO_LEN=0.62) — tay nâng ly lên miệng

    Tay trái:
      ang_s = -0.15 → tay hơi về phía trước (không thả thẳng như idle)
      ang_e =  0.10 → khuỷu gập nhẹ — tư thế chờ tự nhiên

    Đầu hơi nghiêng về phía ly:
      head_x = 0.04 → nghiêng nhẹ sang phải về phía tay cầm ly
    """
    breath = math.sin(t * IDLE_BREATH_FREQ) * IDLE_BREATH_AMP
    sh     = (0.0, TORSO_LEN + breath)

    # Tay phải — IK lock vào target
    re, rh = _arm_ik(*sh,
                     hx=DRINK_HAND_X, hy=DRINK_HAND_Y,
                     side=1,
                     prefer_elbow_up=False)

    # Tay trái — FK idle hơi về trước
    le, lh = _arm(*sh, ang_s=-0.15, ang_e=0.10, side=-1)

    return dict(
        hip      = (0.0, 0.0),
        shoulder = sh,
        head     = (0.04, TORSO_LEN + HEAD_OFFSET + breath),
        #            ↑ đầu nghiêng nhẹ về phía ly
        l_elbow  = le, l_hand = lh,
        r_elbow  = re, r_hand = rh,
        **_STAND_LEGS,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Eat
# ══════════════════════════════════════════════════════════════════════════════

def pose_eat(t: float = 0) -> "Keypoints":
    """
    Ăn — tay phải IK đưa đũa/thìa vào miệng, tay trái giữ bát.

    IK target: (EAT_HAND_X=0.05, EAT_HAND_Y=1.10)
      x=0.05 → gần trục hơn drink (đũa vào miệng thẳng hơn ly)
      y=1.10 → thấp hơn drink một chút (bát thấp hơn ly)

    Tay trái giữ bát:
      IK target phía trái: x=-0.15, y=0.85
      → tay trái giơ ra phía trước, thấp hơn miệng — đúng tư thế cầm bát

    Chuyển động nhai — đầu gật nhẹ theo nhịp ăn:
      head_bob = sin(t * 3.0) * 0.012 → gật đầu 3 Hz (nhịp nhai)
    """
    breath   = math.sin(t * IDLE_BREATH_FREQ) * IDLE_BREATH_AMP
    head_bob = math.sin(t * 3.0) * 0.012   # gật đầu theo nhịp nhai
    sh       = (0.0, TORSO_LEN + breath)

    # Tay phải — IK đưa đũa/thìa vào miệng
    re, rh = _arm_ik(*sh,
                     hx=EAT_HAND_X, hy=EAT_HAND_Y,
                     side=1,
                     prefer_elbow_up=False)

    # Tay trái — IK giữ bát phía trước
    le, lh = _arm_ik(*sh,
                     hx=-0.15, hy=0.85,
                     side=-1,
                     prefer_elbow_up=False)

    return dict(
        hip      = (0.0, 0.0),
        shoulder = sh,
        head     = (0.02, TORSO_LEN + HEAD_OFFSET + breath + head_bob),
        #                  ↑ hơi cúi về phía bát         ↑ gật theo nhịp nhai
        l_elbow  = le, l_hand = lh,
        r_elbow  = re, r_hand = rh,
        **_STAND_LEGS,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Hold
# ══════════════════════════════════════════════════════════════════════════════

def pose_hold(t: float = 0) -> "Keypoints":
    """
    Cầm vật ngang ngực — hai tay IK giữ vật phía trước.

    IK target tay phải: (HOLD_HAND_X=0.20, HOLD_HAND_Y=0.90)
      x=0.20 → xa trục hơn drink/eat — cầm vật ngang ngực, không đưa vào miệng
      y=0.90 → thấp hơn vai — tầm ngực

    IK target tay trái: (-HOLD_HAND_X, HOLD_HAND_Y)
      Đối xứng tay phải → hai tay cùng giữ một vật

    Thở làm vật dao động nhẹ:
      Cả hai IK target dịch chuyển theo breath → vật trông như đang được giữ thật
      thay vì tay chuyển động mà vật đứng yên.

    Nhịp thở tay: breath ảnh hưởng đến shoulder_y → IK tự điều chỉnh khuỷu
      Không cần điều chỉnh thủ công — IK solver tự xử lý.
    """
    breath = math.sin(t * IDLE_BREATH_FREQ) * IDLE_BREATH_AMP
    sh     = (0.0, TORSO_LEN + breath)

    # Target dịch theo breath để vật trông như được giữ cùng cơ thể
    hold_y = HOLD_HAND_Y + breath * 0.5   # vật dao động 50% biên độ thở

    # Tay phải — IK
    re, rh = _arm_ik(*sh,
                     hx= HOLD_HAND_X, hy=hold_y,
                     side= 1,
                     prefer_elbow_up=False)

    # Tay trái — IK đối xứng
    le, lh = _arm_ik(*sh,
                     hx=-HOLD_HAND_X, hy=hold_y,
                     side=-1,
                     prefer_elbow_up=False)

    return dict(
        hip      = (0.0, 0.0),
        shoulder = sh,
        head     = (0.0, TORSO_LEN + HEAD_OFFSET + breath),
        l_elbow  = le, l_hand = lh,
        r_elbow  = re, r_hand = rh,
        **_STAND_LEGS,
    )