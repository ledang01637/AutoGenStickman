# src/core/animation/constants.py
"""
constants.py — Toàn bộ hằng số của animation engine.

Tổ chức thành 4 nhóm:
  1. ANATOMY      — tỷ lệ xương người, bất biến tuyệt đối, dùng bởi _arm/_leg/IK solver
  2. STANDING     — preset chân đứng thẳng, dùng bởi mọi pose không có locomotion
  3. ANIMATION    — biên độ và tần số cho từng nhóm pose (walk/run/idle)
  4. IK TARGETS   — tọa độ đích cho bàn tay trong các pose tương tác (drink/eat/hold)

Quy tắc:
  - Không import gì vào file này — zero dependency
  - Không thay đổi giá trị ANATOMY trong runtime; thay đổi sẽ phá vỡ IK solver
  - Mọi magic number trong poses/*.py phải được đặt tên ở đây
"""

import math
from typing import Callable


Keypoints = dict[str, tuple[float, float]]
PoseFn    = Callable[[float], Keypoints]

# ══════════════════════════════════════════════════════════════════════════════
# 1. ANATOMY — Tỷ lệ xương người
#
# Đơn vị: pose space units (không phải pixel, không phải cm)
# Gốc tọa độ (0, 0) đặt tại hông (hip)
# Tỷ lệ giữa các xương phản ánh người trưởng thành thực tế
#
# Dùng bởi:
#   - _arm()     → FK tay: LEN_ARM, LEN_FOREARM
#   - _leg()     → FK chân: LEN_THIGH, LEN_CALF
#   - _arm_ik()  → IK solver: LEN_ARM, LEN_FOREARM (Law of Cosines)
#   - pose_*()   → shoulder_y = TORSO_LEN + bob
# ══════════════════════════════════════════════════════════════════════════════

LEN_THIGH    = 0.45   # hip    → knee   (đùi)
LEN_CALF     = 0.47   # knee   → foot   (ống chân, dài hơn đùi — đúng giải phẫu)
LEN_ARM      = 0.35   # shoulder → elbow (cánh tay trên)
LEN_FOREARM  = 0.32   # elbow  → hand   (cẳng tay)
TORSO_LEN    = 0.62   # hip    → shoulder, BẤT BIẾN — không đổi giữa các frame

HEAD_RADIUS  = 0.13   # bán kính đầu khi vẽ Circle patch
HEAD_OFFSET  = 0.46   # shoulder → tâm đầu (dọc trục y)
#   → head_y = TORSO_LEN + HEAD_OFFSET + bob


# ══════════════════════════════════════════════════════════════════════════════
# 2. STANDING — Preset chân đứng thẳng
#
# Precompute sẵn 4 keypoints cho tư thế đứng thẳng không gập gối.
# Dùng **_STAND_LEGS để unpack thẳng vào return dict của pose.
#
# Dùng bởi: pose_idle, pose_drink, pose_eat, pose_hold, pose_talk, pose_shrug
# KHÔNG dùng bởi: pose_walk, pose_run, pose_jump (chân tự tính qua _leg())
# ══════════════════════════════════════════════════════════════════════════════

_X_L = -0.03   # offset ngang chân trái (âm = sang trái)
_X_R =  0.03   # offset ngang chân phải (dương = sang phải)
                # ≠ 0 để hai chân không chồng lên nhau khi vẽ

_KY  = -LEN_THIGH              # knee_y = -0.45  (thẳng xuống từ hip)
_FY  = -LEN_THIGH - LEN_CALF   # foot_y = -0.92  (đáy, chạm đất)

_STAND_LEGS = dict(
    l_knee=(_X_L, _KY), l_foot=(_X_L, _FY),
    r_knee=(_X_R, _KY), r_foot=(_X_R, _FY),
)


# ══════════════════════════════════════════════════════════════════════════════
# 3. ANIMATION — Biên độ và tần số cho từng nhóm pose
#
# Cấu trúc tên: {POSE}_{PHẦN}_AMP hoặc {POSE}_SPEED
#   AMP   = biên độ dao động (radian cho góc, units cho vị trí)
#   SPEED = hệ số nhân thời gian t → tần số chu kỳ (cao hơn = nhanh hơn)
#   LEAN  = độ nghiêng cố định của torso (không dao động)
#   COMPRESS = torso rút ngắn theo chiều dọc khi lean
#
# Pha mặc định: w = t * SPEED + π/2
#   → offset π/2 đảm bảo frame đầu tiên (t=0) bắt đầu giữa stride
#   → tránh hiện tượng giật khi animation bắt đầu
# ══════════════════════════════════════════════════════════════════════════════

# ── Walk ──────────────────────────────────────────────────────────────────────
# Đi bộ bình thường: tay-chân ngược pha, bob 2× tần số bước
WALK_SPEED        = 5.0    # tần số chu kỳ bước
WALK_HIP_AMP      = 0.65   # biên độ góc hông     (radian, ≈ ±37°)
WALK_SHOULDER_AMP = 0.45   # biên độ góc vai/tay  (nhỏ hơn hông — đúng thực tế)
WALK_KNEE_AMP     = 1.00   # biên độ gập gối      (max(0, ...) → chỉ gập về sau)
WALK_ELBOW_AMP    = 0.50   # biên độ gập khuỷu
WALK_BOB_AMP      = 0.018  # nảy dọc              (2× tần số bước)
WALK_SWAY_AMP     = 0.012  # lắc ngang            (1× tần số bước)

# ── Run ───────────────────────────────────────────────────────────────────────
# Chạy: biên độ lớn hơn walk, torso đổ về trước (lean)
RUN_SPEED         = 8.0    # nhanh hơn walk
RUN_HIP_AMP       = 0.90   # hông xoay nhiều hơn
RUN_SHOULDER_AMP  = 0.65   # tay swing mạnh hơn
RUN_KNEE_AMP      = 1.40   # gối gập sâu hơn
RUN_ELBOW_AMP     = 0.70   # khuỷu gập nhiều hơn
RUN_BOB_AMP       = 0.030  # nảy mạnh hơn walk
RUN_LEAN          = 0.10   # torso đổ về trước (offset x cố định)
RUN_TORSO_COMPRESS = 0.02  # torso rút ngắn do lean
                            # → shoulder_y = TORSO_LEN - RUN_TORSO_COMPRESS + bob
RUN_HEAD_LEAN_AMP = 1.5    # đầu đổ về trước nhiều hơn vai (quán tính cổ)

# ── Idle / Breath ─────────────────────────────────────────────────────────────
# Đứng yên: chỉ có breath cycle, không có locomotion
IDLE_BREATH_FREQ  = 1.8    # tần số thở (Hz) — ~18 nhịp/phút
IDLE_BREATH_AMP   = 0.008  # biên độ nhô ngực — đủ thấy, không lộ liễu


# ══════════════════════════════════════════════════════════════════════════════
# 4. IK TARGETS — Tọa độ đích cho bàn tay trong pose tương tác
#
# Tọa độ tính từ gốc hip (0, 0):
#   x: dương = sang phải, gần 0 = gần trục giữa cơ thể (cross-body rule)
#   y: dương = lên trên,  y > TORSO_LEN nghĩa là cao hơn vai
#
# Cross-body rule: tay đưa vào miệng → x nhỏ (gần trục 0)
#   → IK solver tự flare khuỷu ra ngoài để tránh chest clipping
#
# Dùng bởi: pose_drink, pose_eat, pose_hold
# Truyền vào: _arm_ik(sh_x, sh_y, TARGET_X, TARGET_Y, side=1)
# ══════════════════════════════════════════════════════════════════════════════

DRINK_HAND_X = 0.08   # gần trục miệng, hơi sang phải
DRINK_HAND_Y = 1.15   # cao hơn vai — tay nâng ly lên miệng

EAT_HAND_X   = 0.05   # gần trục miệng hơn drink (đũa/thìa vào thẳng hơn)
EAT_HAND_Y   = 1.10   # thấp hơn drink một chút — bát/đĩa thấp hơn ly

HOLD_HAND_X  = 0.20   # xa trục hơn — cầm vật ngang ngực, không đưa vào miệng
HOLD_HAND_Y  = 0.90   # thấp hơn vai — tầm ngực, không giơ cao