"""
poses.py — Stickman pose definitions

Kiến trúc Lower / Upper / Combine
══════════════════════════════════════════════════════════════════════════════
lower_*(t)         → hip, l_knee, l_foot, r_knee, r_foot
upper_*(t, hip_y)  → shoulder, head, l_elbow, l_hand, r_elbow, r_hand
combine(lower, upper, t) → Keypoints đầy đủ
"""

import math
from typing import Callable

Keypoints = dict[str, tuple[float, float]]
PoseFn    = Callable[[float], Keypoints]

# ── Bone lengths ───────────────────────────────────────────────────────────────
#Các hằng số không thay đổi chuẩn dáng người thật
LEN_THIGH, LEN_CALF    = 0.45, 0.47
LEN_ARM,   LEN_FOREARM = 0.35, 0.32
TORSO_LEN          = 0.62

# ── Hand positions (FK) ───────────────────────────────────────────────────────
DRINK_HAND_X, DRINK_HAND_Y = 0.08, 1.15
EAT_HAND_X,   EAT_HAND_Y   = 0.05, 1.10
HOLD_HAND_X,  HOLD_HAND_Y  = 0.20, 0.90

# ── Walk / Run parameters (FK) ───────────────────────────────────────────────
WALK_SPEED        = 5.0
WALK_HIP_AMP      = 0.65
WALK_SHOULDER_AMP = 0.45
WALK_KNEE_AMP     = 1.00
WALK_ELBOW_AMP    = 0.50
WALK_BOB_AMP      = 0.018
WALK_SWAY_AMP     = 0.012
HEAD_OFFSET       = 0.46

# ── Standing leg preset ────────────────────────────────────────────────────────
_X_L, _X_R = -0.03,  0.03
_KY         = -LEN_THIGH
_FY         = -LEN_THIGH - LEN_CALF
_STAND_LEGS = dict(
    l_knee=(_X_L, _KY), l_foot=(_X_L, _FY),
    r_knee=(_X_R, _KY), r_foot=(_X_R, _FY),
)


# ── FK / IK helpers ───────────────────────────────────────────────────────────

def _arm(sh_x: float, sh_y: float, ang_s: float, ang_e: float, side: int):
    """FK tay từ shoulder. side: +1=phải, -1=trái."""
    ex = sh_x + _X_R * side + LEN_ARM     * math.sin(ang_s)
    ey = sh_y               - LEN_ARM     * math.cos(ang_s)
    hx = ex                 + LEN_FOREARM * math.sin(ang_s + ang_e)
    hy = ey                 - LEN_FOREARM * math.cos(ang_s + ang_e)
    return (ex, ey), (hx, hy)


def _arm_ik(sh_x: float, sh_y: float, hx: float, hy: float,
            side: int, prefer_elbow_up: bool = False):
    """
    IK 2D tay — tính elbow từ target hand position.

    So sánh 2 solutions hình học, chọn theo prefer_elbow_up:
      False (default) → elbow_y thấp nhất  (ăn/uống thường — Rule 3)
      True            → elbow_y cao nhất   (chugging/ném — ngoại lệ Rule 3)

    side: +1=phải, -1=trái
    real_sh_x = sh_x + 0.16 * side  (vai thật trong front-view)
    """
    real_sh_x = sh_x + 0.16 * side
    real_sh_y = sh_y - 0.02

    dx = hx - real_sh_x
    dy = hy - real_sh_y
    d  = math.hypot(dx, dy)
    d  = min(d, LEN_ARM + LEN_FOREARM - 0.001)

    cos_a = (LEN_ARM**2 + d**2 - LEN_FOREARM**2) / (2 * LEN_ARM * d)
    cos_a = max(-1.0, min(1.0, cos_a))
    alpha  = math.acos(cos_a)
    theta  = math.atan2(dy, dx)

    ea1 = theta + alpha
    ea2 = theta - alpha
    ey1 = real_sh_y + LEN_ARM * math.sin(ea1)
    ey2 = real_sh_y + LEN_ARM * math.sin(ea2)

    # Chọn solution theo yêu cầu — KHÔNG may mắn
    if prefer_elbow_up:
        ea = ea1 if ey1 > ey2 else ea2
    else:
        ea = ea1 if ey1 < ey2 else ea2

    ex = real_sh_x + LEN_ARM * math.cos(ea)
    ey = real_sh_y + LEN_ARM * math.sin(ea)
    return (ex, ey), (hx, hy)


def _leg(hip_x: float, hip_y: float, ang_h: float, ang_k: float, side: int):
    """FK chân từ hip. ang_k âm = gập gối về sau (anatomical constraint)."""
    kx = hip_x + _X_R * side + LEN_THIGH * math.sin(ang_h)
    ky = hip_y               - LEN_THIGH * math.cos(ang_h)
    fx = kx                  + LEN_CALF  * math.sin(ang_h + ang_k)
    fy = ky                  - LEN_CALF  * math.cos(ang_h + ang_k)
    return (kx, ky), (fx, fy)


# ══════════════════════════════════════════════════════════════════════════════
# LOWER BODY
# ══════════════════════════════════════════════════════════════════════════════

def lower_stand(t: float = 0) -> dict:
    bob  = math.sin(t * 1.5) * 0.008
    sway = math.sin(t * 1.5) * 0.006
    return dict(hip=(sway, bob), **_STAND_LEGS)


def lower_sit_floor(t: float = 0) -> dict:
    bob   = math.sin(t * 1.5) * 0.005
    hip_y = -0.65 + bob
    lk, lf = _leg(0, hip_y, 1.2, -2.4, -1)
    rk, rf = _leg(0, hip_y, 1.2, -2.4,  1)
    return dict(hip=(0, hip_y), l_knee=lk, l_foot=lf, r_knee=rk, r_foot=rf)


def lower_sit_chair(t: float = 0) -> dict:
    bob   = math.sin(t * 1.5) * 0.005
    hip_y = -0.30 + bob
    lk, lf = _leg(0, hip_y,  math.pi * 0.48, -math.pi * 0.50, -1)
    rk, rf = _leg(0, hip_y,  math.pi * 0.48, -math.pi * 0.50,  1)
    return dict(hip=(0, hip_y), l_knee=lk, l_foot=lf, r_knee=rk, r_foot=rf)


def lower_squat(t: float = 0) -> dict:
    bob   = math.sin(t * 1.5) * 0.005
    hip_y = -0.48 + bob
    return dict(
        hip=(0, hip_y),
        l_knee=(-0.30, hip_y - 0.15), r_knee=( 0.30, hip_y - 0.15),
        l_foot=(-0.24, hip_y - 0.52), r_foot=( 0.24, hip_y - 0.52),
    )


def lower_sit_legs_straight(t: float = 0) -> dict:
    bob   = math.sin(t * 1.2) * 0.004
    hip_y = -0.60 + bob
    lk, lf = _leg(0, hip_y, math.pi * 0.50, -0.05, -1)
    rk, rf = _leg(0, hip_y, math.pi * 0.50, -0.05,  1)
    return dict(hip=(0, hip_y), l_knee=lk, l_foot=lf, r_knee=rk, r_foot=rf)


def lower_sit_crosslegged(t: float = 0) -> dict:
    bob   = math.sin(t * 1.2) * 0.004
    hip_y = -0.62 + bob
    return dict(
        hip=(0, hip_y),
        l_knee=(-0.24, hip_y - 0.10), r_knee=( 0.24, hip_y - 0.10),
        l_foot=( 0.08, hip_y - 0.28), r_foot=(-0.08, hip_y - 0.28),
    )


def lower_squat_straight(t: float = 0) -> dict:
    bob   = math.sin(t * 1.5) * 0.005
    hip_y = -0.30 + bob
    return dict(
        hip=(0, hip_y),
        l_knee=(-0.20, hip_y - 0.20), r_knee=( 0.20, hip_y - 0.20),
        l_foot=(-0.16, hip_y - 0.58), r_foot=( 0.16, hip_y - 0.58),
    )


# ══════════════════════════════════════════════════════════════════════════════
# UPPER BODY — SIDE VIEW (FK)
# ══════════════════════════════════════════════════════════════════════════════

def upper_idle(t: float = 0, hip_y: float = 0.0) -> dict:
    w    = t * 1.5
    bob  = math.sin(w) * 0.008
    sway = math.sin(w) * 0.006
    sh   = (sway * 0.5, hip_y + TORSO_LEN + bob)
    le, lh = _arm(*sh,  0.18, 0.15, -1)
    re, rh = _arm(*sh,  0.18, 0.15,  1)
    return dict(
        shoulder=sh,
        head=(sway * 0.3, hip_y + TORSO_LEN + 0.46 + bob),
        l_elbow=le, l_hand=lh,
        r_elbow=re, r_hand=rh,
    )


def upper_eat_chopsticks(t: float = 0, hip_y: float = 0.0) -> dict:
    """Side view — ăn đũa."""
    w   = t * 5.0
    bob = math.sin(w) * 0.01
    sh  = (0.0, hip_y + TORSO_LEN + bob)
    le, lh = _arm(*sh, 0.8, 1.6, -1)
    action = math.sin(w)
    re, rh = _arm(*sh, 1.0 + 0.2 * action, 1.4 + 0.4 * action, 1)
    return dict(
        shoulder=sh,
        head=(0.05, hip_y + TORSO_LEN + 0.46 + bob),
        l_elbow=le, l_hand=lh,
        r_elbow=re, r_hand=rh,
    )


def upper_eat_skewer(t: float = 0, hip_y: float = 0.0) -> dict:
    """Side view — tuốt xiên nướng."""
    w    = t * 4.0
    pull = max(0.0, math.sin(w))
    sh   = (0.02, hip_y + TORSO_LEN)
    le, lh = _arm(*sh, 0.2, 0.1, -1)
    re, rh = _arm(*sh, 1.2 + 0.3 * pull, 1.8 - 1.4 * pull, 1)
    return dict(
        shoulder=sh,
        head=(0.12 - 0.08 * pull, hip_y + TORSO_LEN + 0.43),
        l_elbow=le, l_hand=lh,
        r_elbow=re, r_hand=rh,
    )


def upper_drink_chug(t: float = 0, hip_y: float = 0.0) -> dict:
    """Side view — uống dốc ngược."""
    bob = math.sin(t * 8.0) * 0.005
    sh  = (-0.05, hip_y + TORSO_LEN)
    le, lh = _arm(*sh, 0.1, 0.1, -1)
    re, rh = _arm(*sh, 1.5, 1.8,  1)
    return dict(
        shoulder=sh,
        head=(-0.15, hip_y + TORSO_LEN + 0.43 + bob),
        l_elbow=le, l_hand=lh,
        r_elbow=re, r_hand=rh,
    )


# ══════════════════════════════════════════════════════════════════════════════
# UPPER BODY — FRONT VIEW (IK, so sánh 2 solutions — không may mắn)
# ══════════════════════════════════════════════════════════════════════════════

def upper_eat_chopsticks_front(t: float = 0, hip_y: float = 0.0) -> dict:
    """
    Front view — ăn đũa.

    Fix "cánh gà":
    - hand_x = 0.02 (cross-body, không phải 0.16)
    - head_y = TORSO_LEN + 0.40 (cúi đầu lấy đà, giảm d vai→miệng)
    - _arm_ik so sánh 2 solutions, chọn elbow_y thấp nhất
    """
    w      = t * 5.0
    bob    = math.sin(w) * 0.01
    sh     = (0.0, hip_y + TORSO_LEN + bob)
    # Cúi đầu khi ăn — giảm khoảng cách vai→miệng để IK có "độ chùng"
    head_y = hip_y + TORSO_LEN + 0.40 + bob

    # Tay trái bưng bát cố định trước ngực
    le, lh = _arm_ik(*sh, hx=0.0, hy=sh[1] - 0.05, side=-1)

    # Tay phải: cross-body đưa vào trung tâm mặt
    action = math.sin(w)   # -1=bát, +1=miệng
    hand_x = 0.02
    hand_y = sh[1] + 0.08 + 0.22 * action
    re, rh = _arm_ik(*sh, hx=hand_x, hy=hand_y, side=1)

    return dict(shoulder=sh, head=(0.0, head_y),
                l_elbow=le, l_hand=lh, r_elbow=re, r_hand=rh)


def upper_eat_skewer_front(t: float = 0, hip_y: float = 0.0) -> dict:
    """
    Front view — tuốt xiên.

    Fix "cánh gà":
    - Bắt đầu từ miệng hand_x = 0.0 (cross-body), kéo dần ra ngoài
    - head_y cúi xuống 0.40
    - _arm_ik chọn elbow_y thấp nhất
    """
    w      = t * 4.0
    pull   = max(0.0, math.sin(w))
    sh     = (0.0, hip_y + TORSO_LEN)
    head_y = hip_y + TORSO_LEN + 0.40

    # Tay trái thả lỏng / tựa đùi
    le, lh = _arm_ik(*sh, hx=-0.22, hy=sh[1] - 0.28, side=-1)

    # Tay phải: pull=0 → miệng (x=0), pull=1 → kéo ngang phải (x=0.42)
    hand_x = 0.0  + 0.42 * pull
    hand_y = head_y - 0.05 - 0.04 * pull
    re, rh = _arm_ik(*sh, hx=hand_x, hy=hand_y, side=1)

    return dict(shoulder=sh, head=(-0.04 * pull, head_y),
                l_elbow=le, l_hand=lh, r_elbow=re, r_hand=rh)


def upper_drink_chug_front(t: float = 0, hip_y: float = 0.0) -> dict:
    """
    Front view — uống dốc ngược.

    Đây là ngoại lệ Rule 3 (chugging):
    - hand_y > sh_y + 0.3 → prefer_elbow_up=True
    - hand_x = 0.0 (cross-body, cốc đưa vào trung tâm)
    - Đầu ngửa ra sau (head_y tăng)
    """
    bob    = math.sin(t * 8.0) * 0.005
    sh     = (0.0, hip_y + TORSO_LEN)
    head_y = hip_y + TORSO_LEN + 0.50 + bob

    le, lh = _arm_ik(*sh, hx=-0.22, hy=sh[1] - 0.28, side=-1)

    # hand_y = sh[1] + 0.40 > sh[1] + 0.3 → chugging → chọn elbow lên
    hand_y = sh[1] + 0.40 + bob
    re, rh = _arm_ik(*sh, hx=0.0, hy=hand_y, side=1,
                     prefer_elbow_up=(hand_y > sh[1] + 0.3))

    return dict(shoulder=sh, head=(0.0, head_y),
                l_elbow=le, l_hand=lh, r_elbow=re, r_hand=rh)


# ══════════════════════════════════════════════════════════════════════════════
# COMBINE
# ══════════════════════════════════════════════════════════════════════════════

def combine(
    lower_fn: Callable[[float], dict],
    upper_fn:  Callable[..., dict],
    t: float = 0,
) -> Keypoints:
    lower = lower_fn(t)
    hip_y = lower["hip"][1]
    upper = upper_fn(t, hip_y=hip_y)
    return {**lower, **upper}


# ══════════════════════════════════════════════════════════════════════════════
# POSE FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def pose_idle(t: float = 0) -> Keypoints:
    return combine(lower_stand, upper_idle, t)

# ── Đứng ──────────────────────────────────────────────────────────────────────
def pose_stand_eat_chopsticks(t: float = 0) -> Keypoints:
    return combine(lower_stand, upper_eat_chopsticks, t)

def pose_stand_eat_skewer(t: float = 0) -> Keypoints:
    return combine(lower_stand, upper_eat_skewer, t)

def pose_stand_drink_chug(t: float = 0) -> Keypoints:
    return combine(lower_stand, upper_drink_chug, t)

# ── Ngồi bệt ──────────────────────────────────────────────────────────────────
def pose_floor_eat_chopsticks(t: float = 0) -> Keypoints:
    return combine(lower_sit_floor, upper_eat_chopsticks, t)

def pose_floor_eat_skewer(t: float = 0) -> Keypoints:
    return combine(lower_sit_floor, upper_eat_skewer, t)

def pose_floor_drink_chug(t: float = 0) -> Keypoints:
    return combine(lower_sit_floor, upper_drink_chug, t)

# ── Ngồi ghế ──────────────────────────────────────────────────────────────────
def pose_chair_eat_chopsticks(t: float = 0) -> Keypoints:
    return combine(lower_sit_chair, upper_eat_chopsticks, t)

def pose_chair_eat_skewer(t: float = 0) -> Keypoints:
    return combine(lower_sit_chair, upper_eat_skewer, t)

def pose_chair_drink_chug(t: float = 0) -> Keypoints:
    return combine(lower_sit_chair, upper_drink_chug, t)

# ── Ngồi chồm hổm ─────────────────────────────────────────────────────────────
def pose_squat_eat_chopsticks(t: float = 0) -> Keypoints:
    return combine(lower_squat, upper_eat_chopsticks_front, t)

def pose_squat_eat_skewer(t: float = 0) -> Keypoints:
    return combine(lower_squat, upper_eat_skewer_front, t)

def pose_squat_drink_chug(t: float = 0) -> Keypoints:
    return combine(lower_squat, upper_drink_chug_front, t)

# ── Ngồi chân duỗi thẳng ──────────────────────────────────────────────────────
def pose_legs_straight_eat_chopsticks(t: float = 0) -> Keypoints:
    return combine(lower_sit_legs_straight, upper_eat_chopsticks, t)

def pose_legs_straight_eat_skewer(t: float = 0) -> Keypoints:
    return combine(lower_sit_legs_straight, upper_eat_skewer, t)

def pose_legs_straight_drink_chug(t: float = 0) -> Keypoints:
    return combine(lower_sit_legs_straight, upper_drink_chug, t)

# ── Ngồi khoanh chân ──────────────────────────────────────────────────────────
def pose_crosslegged_eat_chopsticks(t: float = 0) -> Keypoints:
    return combine(lower_sit_crosslegged, upper_eat_chopsticks_front, t)

def pose_crosslegged_eat_skewer(t: float = 0) -> Keypoints:
    return combine(lower_sit_crosslegged, upper_eat_skewer_front, t)

def pose_crosslegged_drink_chug(t: float = 0) -> Keypoints:
    return combine(lower_sit_crosslegged, upper_drink_chug_front, t)

# ── Ngồi xổm vỉa hè ───────────────────────────────────────────────────────────
def pose_squat_straight_eat_chopsticks(t: float = 0) -> Keypoints:
    return combine(lower_squat_straight, upper_eat_chopsticks_front, t)

def pose_squat_straight_eat_skewer(t: float = 0) -> Keypoints:
    return combine(lower_squat_straight, upper_eat_skewer_front, t)

def pose_squat_straight_drink_chug(t: float = 0) -> Keypoints:
    return combine(lower_squat_straight, upper_drink_chug_front, t)

# ── Poses đặc biệt (logic riêng) ──────────────────────────────────────────────

def pose_walk(t: float = 0) -> Keypoints:
    w    = t * WALK_SPEED + math.pi / 2
    bob  = math.sin(w * 2.0) * WALK_BOB_AMP
    sway = math.sin(w)       * WALK_SWAY_AMP

    ah_r = -WALK_HIP_AMP      * math.sin(w)
    ah_l = -WALK_HIP_AMP      * math.sin(w + math.pi)
    ak_r = -WALK_KNEE_AMP     * max(0.0, -math.cos(w - 0.4))
    ak_l = -WALK_KNEE_AMP     * max(0.0, -math.cos(w + math.pi - 0.4))
    as_l =  WALK_SHOULDER_AMP * math.sin(w)
    as_r =  WALK_SHOULDER_AMP * math.sin(w + math.pi)
    ae_l =  WALK_ELBOW_AMP    * max(0.0, math.sin(w))
    ae_r =  WALK_ELBOW_AMP    * max(0.0, math.sin(w + math.pi))

    sh = (sway * 0.5, TORSO_LEN + bob)                      
    le, lh = _arm(*sh, as_l, ae_l, -1)
    re, rh = _arm(*sh, as_r, ae_r,  1)
    lk, lf = _leg(0, 0, ah_l, ak_l, -1)
    rk, rf = _leg(0, 0, ah_r, ak_r,  1)
    return dict(
        hip      = (sway, bob),
        shoulder = sh,
        head     = (sway * 0.3, TORSO_LEN + HEAD_OFFSET + bob), 
        l_elbow=le, l_hand=lh, r_elbow=re, r_hand=rh,
        l_knee=lk,  l_foot=lf, r_knee=rk,  r_foot=rf,
    )

def pose_run(t: float = 0) -> Keypoints:
    """Chạy FK — biên độ lớn, người đổ về trước."""
    w    = t * 8.0 + math.pi / 2
    bob  = math.sin(w * 2.0) * 0.030
    lean = 0.10

    ah_r = -0.90 * math.sin(w);            ah_l = -0.90 * math.sin(w + math.pi)
    ak_r = -1.40 * max(0.0, -math.cos(w - 0.4))
    ak_l = -1.40 * max(0.0, -math.cos(w + math.pi - 0.4))
    as_l =  0.65 * math.sin(w);            as_r =  0.65 * math.sin(w + math.pi)
    ae_l =  0.70 * max(0.0, math.sin(w));  ae_r =  0.70 * max(0.0, math.sin(w + math.pi))

    sh = (lean, 0.60 + bob)
    le, lh = _arm(*sh, as_l, ae_l, -1)
    re, rh = _arm(*sh, as_r, ae_r,  1)
    lk, lf = _leg(0, 0, ah_l, ak_l, -1)
    rk, rf = _leg(0, 0, ah_r, ak_r,  1)
    return dict(hip=(lean * 0.5, bob), shoulder=sh, head=(lean * 1.5, 1.05 + bob),
                l_elbow=le, l_hand=lh, r_elbow=re, r_hand=rh,
                l_knee=lk, l_foot=lf, r_knee=rk, r_foot=rf)


def pose_shocked(t: float = 0) -> Keypoints:
    s  = 1.0 + math.sin(t * 8) * 0.04
    sh = (0, 0.62 * s)
    le, lh = _arm(*sh, -0.90, 0.20, -1)
    re, rh = _arm(*sh, -0.90, 0.20,  1)
    return dict(hip=(0, 0), shoulder=sh, head=(0, 1.10 * s),
                l_elbow=le, l_hand=lh, r_elbow=re, r_hand=rh, **_STAND_LEGS)


def pose_facepalm(t: float = 0) -> Keypoints:
    sh = (0, 0.62)
    le, lh = _arm(*sh,  0.18, 0.15, -1)
    re, rh = _arm(*sh, -0.85, 0.90,  1)
    return dict(hip=(0, 0), shoulder=sh, head=(0, 1.08),
                l_elbow=le, l_hand=lh, r_elbow=re, r_hand=rh, **_STAND_LEGS)


def pose_cry(t: float = 0) -> Keypoints:
    sob = math.sin(t * 6.0) * 0.018
    sh  = (0, 0.56 + sob)
    le, lh = _arm(*sh, -0.70, 0.75, -1)
    re, rh = _arm(*sh, -0.70, 0.75,  1)
    return dict(hip=(0, 0), shoulder=sh, head=(0, 1.02 + sob),
                l_elbow=le, l_hand=lh, r_elbow=re, r_hand=rh, **_STAND_LEGS)


def pose_point_right(t: float = 0) -> Keypoints:
    sh = (0, 0.62)
    le, lh = _arm(*sh, 0.18, 0.15, -1)
    re, rh = _arm(*sh, 0.55, 0.00,  1)
    return dict(hip=(0, 0), shoulder=sh, head=(0, 1.08),
                l_elbow=le, l_hand=lh, r_elbow=re, r_hand=rh, **_STAND_LEGS)


def pose_dance(t: float = 0) -> Keypoints:
    a       = math.sin(t * 4.0)
    b       = math.cos(t * 4.0)
    hip_bob = abs(a) * 0.06
    sh      = (a * 0.04, 0.62 + hip_bob)
    le, lh  = _arm(*sh, -0.60 - b * 0.30, 0.10, -1)
    re, rh  = _arm(*sh, -0.60 + b * 0.30, 0.10,  1)
    lk = (_X_L + a * 0.08, _KY + abs(a) * 0.10)
    lf = (_X_L + a * 0.10, _FY + abs(a) * 0.12)
    rk = (_X_R - a * 0.08, _KY + abs(b) * 0.10)
    rf = (_X_R - a * 0.10, _FY + abs(b) * 0.12)
    return dict(hip=(0, hip_bob), shoulder=sh, head=(a * 0.04, 1.08 + hip_bob),
                l_elbow=le, l_hand=lh, r_elbow=re, r_hand=rh,
                l_knee=lk, l_foot=lf, r_knee=rk, r_foot=rf)


def pose_explain(t: float = 0) -> Keypoints:
    """Thuyết minh — tay phải đưa ngang, gật đầu nhẹ."""
    bob   = math.sin(t * 3.5) * 0.012
    swing = math.sin(t * 3.5) * 0.018
    sh    = (0, 0.62)
    le, lh = _arm(*sh, 0.18, 0.15, -1)
    re, rh = _arm(*sh, 0.55 + swing * 0.3, 0.0, 1)
    return dict(hip=(0, 0), shoulder=sh, head=(0, 1.08 + bob),
                l_elbow=le, l_hand=lh, r_elbow=re, r_hand=rh, **_STAND_LEGS)


def pose_shrug(t: float = 0) -> Keypoints:
    """Nhún vai bất lực — vai nhô lên, tay giang ra."""
    shrug = 0.04 + math.sin(t * 4.0) * 0.008
    # vai nhô lên = sh_y tăng so với TORSO_LEN (hip_y=0 → sh_y = 0.62 + shrug)
    sh    = (0, 0.62 + shrug)
    le, lh = _arm(*sh, -0.55, 0.0, -1)
    re, rh = _arm(*sh, -0.55, 0.0,  1)
    return dict(hip=(0, 0), shoulder=sh, head=(0, 1.08 + shrug),
                l_elbow=le, l_hand=lh, r_elbow=re, r_hand=rh, **_STAND_LEGS)


# ══════════════════════════════════════════════════════════════════════════════
# REGISTRY
# ══════════════════════════════════════════════════════════════════════════════

POSE_WALK_PARAMS = {
    "walk": {
        "speed":      5.0,    # rad/s — w = t * speed
        "hip_amp":    0.65,   # biên độ góc đùi
        "cycle_s":    2 * math.pi / 5.0,   # 1.2566s
        "stride_local": 1.12,              # tính từ FK ở trên
        "velocity_local": 1.12 / (2 * math.pi / 5.0),  # ≈ 0.891
    },
    "run": {
        "speed":      8.0,
        "hip_amp":    0.90,
        "cycle_s":    2 * math.pi / 8.0,   # 0.785s
        "stride_local": 1.55,
        "velocity_local": 1.55 / (2 * math.pi / 8.0),  # ≈ 1.974
    },
}

POSE_FN: dict[str, PoseFn] = {
    "idle":                          pose_idle,
    "walk":                          pose_walk,
    "run":                           pose_run,

}

POSE_NAMES = list(POSE_FN.keys())

LOWER_FN = {
    "stand":          lower_stand,
    "sit_floor":      lower_sit_floor,
    "sit_chair":      lower_sit_chair,
    "squat":          lower_squat,
    "legs_straight":  lower_sit_legs_straight,
    "crosslegged":    lower_sit_crosslegged,
    "squat_straight": lower_squat_straight,
}

UPPER_FN = {
    "idle":                   upper_idle,
    "eat_chopsticks":         upper_eat_chopsticks,
    "eat_skewer":             upper_eat_skewer,
    "drink_chug":             upper_drink_chug,
    "eat_chopsticks_front":   upper_eat_chopsticks_front,
    "eat_skewer_front":       upper_eat_skewer_front,
    "drink_chug_front":       upper_drink_chug_front,
}


def get_pose(name: str, t: float = 0) -> Keypoints:
    return POSE_FN.get(name, pose_idle)(t)


def get_combined(lower: str, upper: str, t: float = 0) -> Keypoints:
    return combine(LOWER_FN.get(lower, lower_stand),
                   UPPER_FN.get(upper, upper_idle), t)


def lerp_keypoints(kp_a: Keypoints, kp_b: Keypoints, alpha: float) -> Keypoints:
    return {
        k: (
            kp_a[k][0] + (kp_b.get(k, kp_a[k])[0] - kp_a[k][0]) * alpha,
            kp_a[k][1] + (kp_b.get(k, kp_a[k])[1] - kp_a[k][1]) * alpha,
        )
        for k in kp_a
    }