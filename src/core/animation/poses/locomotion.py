"""
poses/locomotion.py — Các pose di chuyển: walk, run.

Đặc điểm chung của locomotion poses:
  - Dùng FK thuần (không có IK) — chân và tay tính từ góc
  - Tay-chân ngược pha: chân phải về trước → tay trái về trước (+π offset)
  - Bob ở 2× tần số bước, sway ở 1× tần số bước
  - Knee Constraint được enforce tại đây: ang_k = -AMP * max(0, -cos(...))
  - Head attenuation: đầu dao động bằng 30% biên độ hông (tránh trông say rượu)

Công thức pha chung:
  w = t * SPEED + π/2
  offset π/2 → frame đầu (t=0) bắt đầu giữa stride, không giật khi bắt đầu
"""

import math

from ..constants import (
    Keypoints, 
    TORSO_LEN, HEAD_OFFSET,
    WALK_SPEED, WALK_HIP_AMP, WALK_SHOULDER_AMP,
    WALK_KNEE_AMP, WALK_ELBOW_AMP, WALK_BOB_AMP, WALK_SWAY_AMP,
    RUN_SPEED, RUN_HIP_AMP, RUN_SHOULDER_AMP,
    RUN_KNEE_AMP, RUN_ELBOW_AMP, RUN_BOB_AMP,
    RUN_LEAN, RUN_TORSO_COMPRESS, RUN_HEAD_LEAN_AMP,
)
from ..helpers import _arm, _leg

def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def ease_in_out(t: float) -> float:
    """Smoothstep cubic — t ∈ [0,1] → [0,1]."""
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


# ══════════════════════════════════════════════════════════════════════════════
# Walk
# ══════════════════════════════════════════════════════════════════════════════

def pose_walk(t: float = 0) -> "Keypoints":
    """
    Đi bộ FK — tay-chân ngược pha, khuỷu gập đúng hướng.

    Biên độ:
      Hông  ±0.65 rad (≈ ±37°) — range sinh lý học đi bộ bình thường
      Vai   ±0.45 rad           — nhỏ hơn hông, đúng thực tế
      Gối   max 1.00 rad        — chỉ gập về sau (Knee Constraint)
      Khuỷu max 0.50 rad        — chỉ gập khi tay swing về trước

    Center of Mass:
      Bob  = sin(2w) × 0.018   — 2× tần số vì mỗi bước tạo một lần nảy
      Sway = sin(w)  × 0.012   — 1× tần số, biên độ nhỏ hơn bob
      Head = sway × 0.3        — attenuation 30%, giảm dần từ hông lên đầu
    """
    w    = t * WALK_SPEED + math.pi / 2
    bob  = math.sin(w * 2.0) * WALK_BOB_AMP
    sway = math.sin(w)       * WALK_SWAY_AMP

    # ── Góc hông — tay-chân ngược pha (+π) ───────────────────────────────────
    ah_r = -WALK_HIP_AMP * math.sin(w)
    ah_l = -WALK_HIP_AMP * math.sin(w + math.pi)

    # ── Knee Constraint — max(0, -cos) → chỉ gập về sau ──────────────────────
    # -cos(w - 0.4): phase offset 0.4 rad → gối bắt đầu gập trước khi hông
    #                đạt đỉnh, chuẩn bị cho bước tiếp theo
    ak_r = -WALK_KNEE_AMP * max(0.0, -math.cos(w - 0.4))
    ak_l = -WALK_KNEE_AMP * max(0.0, -math.cos(w + math.pi - 0.4))

    # ── Góc vai — cùng pha với chân đối diện ─────────────────────────────────
    as_l =  WALK_SHOULDER_AMP * math.sin(w)
    as_r =  WALK_SHOULDER_AMP * math.sin(w + math.pi)

    # ── Khuỷu — chỉ gập khi tay swing về phía trước ──────────────────────────
    ae_l = WALK_ELBOW_AMP * max(0.0,  math.sin(w))
    ae_r = WALK_ELBOW_AMP * max(0.0,  math.sin(w + math.pi))

    # ── Tọa độ shoulder — sway giảm 50% so với hip ───────────────────────────
    sh = (sway * 0.5, TORSO_LEN + bob)

    # ── Solve FK ──────────────────────────────────────────────────────────────
    le, lh = _arm(*sh, as_l, ae_l, -1)
    re, rh = _arm(*sh, as_r, ae_r,  1)
    lk, lf = _leg(0, 0, ah_l, ak_l, -1)
    rk, rf = _leg(0, 0, ah_r, ak_r,  1)

    return dict(
        hip      = (sway, bob),
        shoulder = sh,
        head     = (sway * 0.3, TORSO_LEN + HEAD_OFFSET + bob),
        l_elbow  = le, l_hand = lh,
        r_elbow  = re, r_hand = rh,
        l_knee   = lk, l_foot = lf,
        r_knee   = rk, r_foot = rf,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Walk push-phase — FK có 4 pha sinh lý học
# ══════════════════════════════════════════════════════════════════════════════

STANCE_END       = 0.45
PUSH_END         = 0.65
SWING_END        = 0.90
PUSH_KNEE_EXTRA  = 0.35
SWING_KNEE_FLEX  = 0.55


def _leg_phase(half_cycle_progress: float):
    """
    half_cycle_progress ∈ [0, 1] → (phase_name, t_local ∈ [0,1])

    Pha:
      stance [0.00, 0.45) — chân chịu lực, giữ cố định
      push   [0.45, 0.65) — cổ chân đẩy, thân tiến
      swing  [0.65, 0.90) — chân bay, gối gập cao
      heel   [0.90, 1.00] — gót tiếp đất nhẹ
    """
    p = half_cycle_progress % 1.0
    if p < STANCE_END:
        return "stance", p / STANCE_END
    if p < PUSH_END:
        return "push",   (p - STANCE_END) / (PUSH_END  - STANCE_END)
    if p < SWING_END:
        return "swing",  (p - PUSH_END)   / (SWING_END - PUSH_END)
    return     "heel",   (p - SWING_END)  / (1.0       - SWING_END)


def _leg_with_push(w: float, side: int):
    """
    FK chân có 4 pha sinh lý học.
    side: +1 = phải, -1 = trái.
    """
    raw = (w / (2.0 * math.pi)) % 1.0
    if side == -1:
        raw = (raw + 0.5) % 1.0      # chân trái lệch nửa chu kỳ

    half          = (raw * 2.0) % 1.0
    phase, tl     = _leg_phase(half)

    if phase == "stance":
        ang_h = -WALK_HIP_AMP * (tl * 2.0 - 1.0) * 0.5
        ang_k = -WALK_KNEE_AMP * max(0.0, 0.1 - abs(ang_h))

    elif phase == "push":
        ang_h = -WALK_HIP_AMP * lerp(0.5, 1.0, tl)
        ang_k = -max(0.0, WALK_KNEE_AMP * (1.0 - tl) - PUSH_KNEE_EXTRA)

    elif phase == "swing":
        ang_h = WALK_HIP_AMP  * lerp(-1.0, 1.0, ease_in_out(tl))
        ang_k = -SWING_KNEE_FLEX * math.sin(tl * math.pi)

    else:  # heel
        ang_h = WALK_HIP_AMP  * lerp(1.0, 0.5, tl)
        ang_k = -WALK_KNEE_AMP * 0.15 * tl

    return _leg(0, 0, ang_h, ang_k, side)


def _hip_push_bob(w: float) -> float:
    """
    Bob dọc bất đối xứng theo push-phase.
    Pha đẩy: thân nâng thêm. Pha swing: thân hơi xuống.
    """
    base_bob  = math.sin(w * 2.0) * WALK_BOB_AMP
    push_lift = math.sin(w)       * WALK_BOB_AMP * 0.6
    return base_bob + push_lift


def pose_walk_push(t: float = 0) -> "Keypoints":
    """
    Đi bộ có push-phase — chân đẩy thân tiến trước khi chân kia swing.

    Khác pose_walk:
      Chân dùng _leg_with_push() thay vì FK sin/cos thuần
      Bob bất đối xứng — nâng rõ hơn ở pha đẩy
      Tay giữ nguyên FK cũ (không đổi)
    """
    w    = t * WALK_SPEED + math.pi / 2
    bob  = _hip_push_bob(w)
    sway = math.sin(w) * WALK_SWAY_AMP

    sh = (sway * 0.5, TORSO_LEN + bob)

    as_l =  WALK_SHOULDER_AMP * math.sin(w)
    as_r =  WALK_SHOULDER_AMP * math.sin(w + math.pi)
    ae_l =  WALK_ELBOW_AMP * max(0.0, math.sin(w))
    ae_r =  WALK_ELBOW_AMP * max(0.0, math.sin(w + math.pi))

    le, lh = _arm(*sh, as_l, ae_l, -1)
    re, rh = _arm(*sh, as_r, ae_r,  1)
    lk, lf = _leg_with_push(w, side=-1)
    rk, rf = _leg_with_push(w, side= 1)

    return dict(
        hip      = (sway, bob),
        shoulder = sh,
        head     = (sway * 0.3, TORSO_LEN + HEAD_OFFSET + bob),
        l_elbow  = le, l_hand = lh,
        r_elbow  = re, r_hand = rh,
        l_knee   = lk, l_foot = lf,
        r_knee   = rk, r_foot = rf,
    )

# ══════════════════════════════════════════════════════════════════════════════
# Run
# ══════════════════════════════════════════════════════════════════════════════

def pose_run(t: float = 0) -> "Keypoints":
    """
    Chạy FK — biên độ lớn hơn walk, torso đổ về trước.

    Khác walk:
      SPEED cao hơn (8.0 vs 5.0) → chu kỳ bước nhanh hơn
      Biên độ tất cả lớn hơn     → chuyển động mạnh hơn
      LEAN cố định = 0.10        → torso nghiêng về trước liên tục
      TORSO_COMPRESS = 0.02      → shoulder_y thấp hơn do nghiêng
      HEAD_LEAN_AMP = 1.5        → đầu đổ nhiều hơn vai (quán tính cổ)

    Center of Mass:
      Không có sway ngang vì lean dọc đã chiếm dominant motion.
      Hip x = LEAN * 0.5 (hông đổ ít hơn vai — điểm tựa ở dưới).
    """
    w   = t * RUN_SPEED + math.pi / 2
    bob = math.sin(w * 2.0) * RUN_BOB_AMP

    # ── Góc hông ──────────────────────────────────────────────────────────────
    ah_r = -RUN_HIP_AMP * math.sin(w)
    ah_l = -RUN_HIP_AMP * math.sin(w + math.pi)

    # ── Knee Constraint — gập sâu hơn walk ───────────────────────────────────
    ak_r = -RUN_KNEE_AMP * max(0.0, -math.cos(w - 0.4))
    ak_l = -RUN_KNEE_AMP * max(0.0, -math.cos(w + math.pi - 0.4))

    # ── Góc vai ───────────────────────────────────────────────────────────────
    as_l =  RUN_SHOULDER_AMP * math.sin(w)
    as_r =  RUN_SHOULDER_AMP * math.sin(w + math.pi)

    # ── Khuỷu — gập nhiều hơn walk ───────────────────────────────────────────
    ae_l = RUN_ELBOW_AMP * max(0.0,  math.sin(w))
    ae_r = RUN_ELBOW_AMP * max(0.0,  math.sin(w + math.pi))

    # ── Shoulder thấp hơn do torso lean + compress ────────────────────────────
    sh_y = TORSO_LEN - RUN_TORSO_COMPRESS + bob
    sh   = (RUN_LEAN, sh_y)

    # ── Solve FK ──────────────────────────────────────────────────────────────
    le, lh = _arm(*sh, as_l, ae_l, -1)
    re, rh = _arm(*sh, as_r, ae_r,  1)
    lk, lf = _leg(0, 0, ah_l, ak_l, -1)
    rk, rf = _leg(0, 0, ah_r, ak_r,  1)

    return dict(
        hip      = (RUN_LEAN * 0.5, bob),
        shoulder = sh,
        head     = (RUN_LEAN * RUN_HEAD_LEAN_AMP,
                    TORSO_LEN - RUN_TORSO_COMPRESS + HEAD_OFFSET + bob),
        l_elbow  = le, l_hand = lh,
        r_elbow  = re, r_hand = rh,
        l_knee   = lk, l_foot = lf,
        r_knee   = rk, r_foot = rf,
    )