"""
validators.py — Animation JSON schema validator
"""

from __future__ import annotations
from typing import Any

# ── Allowed values ─────────────────────────────────────────────────────────────

VALID_BACKGROUNDS = {
    "office", "bedroom", "city_day", "park_day",
    "cafe", "gym", "street_food",
}

VALID_BACKGROUND_VARIANTS = {
    "office":      {"day", "night", "deadline"},
    "bedroom":     {"morning", "night", "lazy"},
    "city_day":    {"morning", "rush_hour", "rain"},
    "park_day":    {"sunny", "evening", "date"},
    "cafe":        {"cozy", "busy", "rainy"},
    "gym":         {"morning", "crowded", "empty"},
    "street_food": {"lunch", "night", "weekend"},
}

VALID_POSES = {
    # Cơ bản
    "idle", "walk", "run", "dance",
    "shocked", "facepalm", "cry", "point_right", "explain", "shrug",
    # Đứng ăn uống
    "stand_eat_chopsticks", "stand_eat_skewer", "stand_drink_chug",
    # Ngồi bệt
    "floor_eat_chopsticks", "floor_eat_skewer", "floor_drink_chug",
    # Ngồi ghế
    "chair_eat_chopsticks", "chair_eat_skewer", "chair_drink_chug",
    # Ngồi chồm hổm
    "squat_eat_chopsticks", "squat_eat_skewer", "squat_drink_chug",
    # Ngồi chân duỗi
    "legs_straight_eat_chopsticks", "legs_straight_eat_skewer", "legs_straight_drink_chug",
    # Ngồi khoanh chân
    "crosslegged_eat_chopsticks", "crosslegged_eat_skewer", "crosslegged_drink_chug",
    # Ngồi xổm vỉa hè
    "squat_straight_eat_chopsticks", "squat_straight_eat_skewer", "squat_straight_drink_chug",
}

VALID_EXPRESSIONS = {
    "neutral", "happy", "sad", "surprised", "angry", "love", "scared",
}

VALID_PROPS = {
    "bowl", "cup", "boba", "bag_food",
    "phone", "laptop", "book", "document",
    "wallet", "money_bag", "coin", "price_tag",
    "broken_heart", "fire", "trophy", "dumbbell",
    "briefcase", "clock",
}

ANCHOR_METADATA: dict[str, dict] = {
    "right_hand":   {"keypoint": "r_hand",   "offset": ( 0.0,   0.0)},
    "left_hand":    {"keypoint": "l_hand",   "offset": ( 0.0,   0.0)},
    "above_head":   {"keypoint": "head",     "offset": ( 0.0,   0.40)},
    "ground_front": {"keypoint": "hip",      "offset": ( 0.40, -0.92)},
    "ground_below": {"keypoint": "hip",      "offset": ( 0.0,  -0.92)},
    "side_right":   {"keypoint": "r_hand",   "offset": ( 1.20,  0.0)},
    "side_left":    {"keypoint": "l_hand",   "offset": (-1.20,  0.0)},
    "front_far":    {"keypoint": "hip",      "offset": ( 0.60, -0.50)},
    "body_center":  {"keypoint": "shoulder", "offset": ( 0.0,   0.0)},
}
VALID_ANCHORS       = set(ANCHOR_METADATA.keys())
ANCHOR_TO_KEYPOINT  = {k: v["keypoint"] for k, v in ANCHOR_METADATA.items()}
ANCHOR_OFFSET       = {k: v["offset"]   for k, v in ANCHOR_METADATA.items()}

SPAWN_POINTS: dict[str, list[dict]] = {
    "office": [
        {"id": "desk_left",   "x": 0.20, "description": "Left workstation"},
        {"id": "desk_center", "x": 0.50, "description": "Center desk"},
        {"id": "desk_right",  "x": 0.80, "description": "Right workstation"},
    ],
    "bedroom": [
        {"id": "bed_left",  "x": 0.25, "description": "Left side of bed"},
        {"id": "bed_right", "x": 0.70, "description": "Right side of bed"},
        {"id": "door",      "x": 0.88, "description": "Near the door"},
    ],
    "city_day": [
        {"id": "sidewalk_left",  "x": 0.15, "description": "Left sidewalk"},
        {"id": "sidewalk_mid",   "x": 0.50, "description": "Center sidewalk"},
        {"id": "sidewalk_right", "x": 0.82, "description": "Right sidewalk"},
    ],
    "park_day": [
        {"id": "bench_left",  "x": 0.22, "description": "Left park bench"},
        {"id": "bench_right", "x": 0.75, "description": "Right park bench"},
        {"id": "path_near",   "x": 0.50, "description": "Center path (near)"},
        {"id": "path_far",    "x": 0.65, "description": "Center path (far)"},
    ],
    "cafe": [
        {"id": "table_left",   "x": 0.20, "description": "Left cafe table"},
        {"id": "table_center", "x": 0.50, "description": "Center cafe table"},
        {"id": "table_right",  "x": 0.78, "description": "Right cafe table"},
        {"id": "counter",      "x": 0.88, "description": "Cashier counter"},
    ],
    "gym": [
        {"id": "machine_left",   "x": 0.18, "description": "Left exercise machine"},
        {"id": "machine_center", "x": 0.50, "description": "Center exercise machine"},
        {"id": "machine_right",  "x": 0.80, "description": "Right exercise machine"},
    ],
    "street_food": [
        {"id": "stall_left",  "x": 0.15, "description": "Left food stall"},
        {"id": "stall_right", "x": 0.82, "description": "Right food stall"},
        {"id": "queue_mid",   "x": 0.48, "description": "Middle of queue"},
        {"id": "queue_back",  "x": 0.62, "description": "Back of queue"},
    ],
}

# ── Limits ─────────────────────────────────────────────────────────────────────
MAX_SCENES        = 20
MAX_KEYFRAMES     = 30
MAX_CAPTIONS      = 20
MAX_PROPS         = 10
MAX_EXTRAS        = 4
MIN_DURATION_MS   = 1000
MAX_DURATION_MS   = 60_000
MAX_VOICEOVER_LEN = 500


# ── Error class ────────────────────────────────────────────────────────────────

class ValidationError(Exception):
    def __init__(self, errors: list[str]):
        self.errors = errors
        msg = f"{len(errors)} validation error(s):\n" + "\n".join(
            f"  [{i+1}] {e}" for i, e in enumerate(errors)
        )
        super().__init__(msg)


# ── Main validator ─────────────────────────────────────────────────────────────

def validate_animation_json(data: Any) -> None:
    errors: list[str] = []

    if not isinstance(data, dict):
        raise ValidationError(["Root phải là object JSON, không phải list/string."])

    if data.get("render_type") != "animation":
        errors.append('render_type phải là "animation".')

    scenes = data.get("scenes")
    if not isinstance(scenes, list) or len(scenes) == 0:
        errors.append('"scenes" phải là array không rỗng.')
        _raise_if(errors)

    if len(scenes) > MAX_SCENES:
        errors.append(f'"scenes" tối đa {MAX_SCENES} scenes, nhận được {len(scenes)}.')

    for idx, scene in enumerate(scenes):
        pfx = f'scenes[{idx}]'

        if not isinstance(scene, dict):
            errors.append(f'{pfx}: phải là object.')
            continue

        if not scene.get("scene_id"):
            errors.append(f'{pfx}: thiếu "scene_id".')

        vo = scene.get("voiceover", "")
        if not isinstance(vo, str):
            errors.append(f'{pfx}.voiceover: phải là string.')
        elif len(vo) > MAX_VOICEOVER_LEN:
            errors.append(f'{pfx}.voiceover: quá dài ({len(vo)} ký tự, tối đa {MAX_VOICEOVER_LEN}).')

        dur = scene.get("duration_ms")
        if not isinstance(dur, (int, float)):
            errors.append(f'{pfx}.duration_ms: phải là số.')
        elif not (MIN_DURATION_MS <= dur <= MAX_DURATION_MS):
            errors.append(f'{pfx}.duration_ms: ngoài khoảng [{MIN_DURATION_MS}, {MAX_DURATION_MS}], nhận {dur}.')

        bg = scene.get("background", "")
        if bg not in VALID_BACKGROUNDS:
            errors.append(f'{pfx}.background: "{bg}" không hợp lệ. Chọn một trong: {sorted(VALID_BACKGROUNDS)}.')
        else:
            bv = scene.get("background_variant", "")
            allowed = VALID_BACKGROUND_VARIANTS.get(bg, set())
            if bv not in allowed:
                errors.append(
                    f'{pfx}.background_variant: "{bv}" không hợp lệ cho "{bg}". '
                    f'Chọn một trong: {sorted(allowed)}.'
                )

        scene_dur = dur if isinstance(dur, (int, float)) else 0

        kfs = scene.get("keyframes")
        if not isinstance(kfs, list) or len(kfs) == 0:
            errors.append(f'{pfx}.keyframes: phải là array không rỗng.')
        else:
            if len(kfs) > MAX_KEYFRAMES:
                errors.append(f'{pfx}.keyframes: tối đa {MAX_KEYFRAMES}, nhận {len(kfs)}.')
            _validate_keyframes(kfs, pfx, scene_dur, errors)

        props = scene.get("props", [])
        if not isinstance(props, list):
            errors.append(f'{pfx}.props: phải là array.')
        else:
            if len(props) > MAX_PROPS:
                errors.append(f'{pfx}.props: tối đa {MAX_PROPS}, nhận {len(props)}.')
            for pi, prop in enumerate(props):
                _validate_prop(prop, f'{pfx}.props[{pi}]', errors)

        caps = scene.get("captions", [])
        if not isinstance(caps, list):
            errors.append(f'{pfx}.captions: phải là array.')
        else:
            if len(caps) > MAX_CAPTIONS:
                errors.append(f'{pfx}.captions: tối đa {MAX_CAPTIONS}, nhận {len(caps)}.')
            for ci, cap in enumerate(caps):
                _validate_caption(cap, f'{pfx}.captions[{ci}]', errors)

        extras = scene.get("extras", [])
        if not isinstance(extras, list):
            errors.append(f'{pfx}.extras: phải là array.')
        else:
            if len(extras) > MAX_EXTRAS:
                errors.append(f'{pfx}.extras: tối đa {MAX_EXTRAS}, nhận {len(extras)}.')
            for ei, extra in enumerate(extras):
                _validate_extra(extra, f'{pfx}.extras[{ei}]', scene_dur, errors)

    _raise_if(errors)


# ── Sub-validators ─────────────────────────────────────────────────────────────

def _validate_keyframes(kfs: list, pfx: str, scene_dur: float,
                        errors: list[str]) -> None:
    prev_t    = -1
    prev_pose = None
    for ki, kf in enumerate(kfs):
        kpfx = f'{pfx}.keyframes[{ki}]'

        if not isinstance(kf, dict):
            errors.append(f'{kpfx}: phải là object.')
            continue

        t = kf.get("t")
        if not isinstance(t, (int, float)):
            errors.append(f'{kpfx}.t: phải là số (ms).')
        else:
            if t < 0:
                errors.append(f'{kpfx}.t: không được âm.')
            if scene_dur > 0 and t > scene_dur:
                errors.append(f'{kpfx}.t: {t} vượt quá duration_ms={scene_dur}.')
            if t < prev_t:
                errors.append(f'{kpfx}.t: keyframes phải tăng dần ({t} < {prev_t}).')
            prev_t = t if isinstance(t, (int, float)) else prev_t

        pose = kf.get("pose", "")
        if pose not in VALID_POSES:
            errors.append(f'{kpfx}.pose: "{pose}" không hợp lệ. Chọn một trong: {sorted(VALID_POSES)}.')
        elif pose == prev_pose:
            errors.append(f'{kpfx}.pose: "{pose}" trùng keyframe trước — nhân vật đứng yên. Dùng pose khác.')
        prev_pose = pose if pose in VALID_POSES else prev_pose

        expr = kf.get("expression", "")
        if expr not in VALID_EXPRESSIONS:
            errors.append(f'{kpfx}.expression: "{expr}" không hợp lệ. Chọn một trong: {sorted(VALID_EXPRESSIONS)}.')

        x = kf.get("x")
        if x is not None and (not isinstance(x, (int, float)) or not (0.0 <= x <= 1.0)):
            errors.append(f'{kpfx}.x: phải là số trong [0.0, 1.0].')


def _validate_extra(extra: Any, pfx: str, scene_dur: float,
                    errors: list[str]) -> None:
    if not isinstance(extra, dict):
        errors.append(f'{pfx}: phải là object.')
        return

    if not extra.get("id"):
        errors.append(f'{pfx}: thiếu "id".')

    x = extra.get("x_default")
    if not isinstance(x, (int, float)) or not (0.0 <= x <= 1.0):
        errors.append(f'{pfx}.x_default: phải là số trong [0.0, 1.0].')

    if not isinstance(extra.get("flip"), bool):
        errors.append(f'{pfx}.flip: phải là boolean.')

    color = extra.get("color")
    if color is not None and not isinstance(color, str):
        errors.append(f'{pfx}.color: phải là string hex color.')

    kfs = extra.get("keyframes")
    if not isinstance(kfs, list) or len(kfs) < 3:
        errors.append(f'{pfx}.keyframes: phải có ít nhất 3 keyframes.')
    else:
        if len(kfs) > MAX_KEYFRAMES:
            errors.append(f'{pfx}.keyframes: tối đa {MAX_KEYFRAMES}, nhận {len(kfs)}.')
        _validate_keyframes(kfs, pfx, scene_dur, errors)


def _validate_prop(prop: Any, pfx: str, errors: list[str]) -> None:
    if not isinstance(prop, dict):
        errors.append(f'{pfx}: phải là object.')
        return

    shape = prop.get("shape", "")
    if shape not in VALID_PROPS:
        errors.append(f'{pfx}.shape: "{shape}" không hợp lệ. Chọn một trong: {sorted(VALID_PROPS)}.')

    anchor = prop.get("anchor", "")
    if anchor not in VALID_ANCHORS:
        errors.append(f'{pfx}.anchor: "{anchor}" không hợp lệ. Chọn một trong: {sorted(VALID_ANCHORS)}.')

    appear_at = prop.get("appear_at", 0)
    if not isinstance(appear_at, (int, float)) or appear_at < 0:
        errors.append(f'{pfx}.appear_at: phải là số không âm (ms).')


def _validate_caption(cap: Any, pfx: str, errors: list[str]) -> None:
    if not isinstance(cap, dict):
        errors.append(f'{pfx}: phải là object.')
        return

    t = cap.get("t")
    if not isinstance(t, (int, float)) or t < 0:
        errors.append(f'{pfx}.t: phải là số không âm (ms).')

    dur = cap.get("duration")
    if not isinstance(dur, (int, float)) or dur <= 0:
        errors.append(f'{pfx}.duration: phải là số dương (ms).')

    text = cap.get("text", "")
    if not isinstance(text, str) or len(text.strip()) == 0:
        errors.append(f'{pfx}.text: phải là string không rỗng.')
    elif len(text) > 200:
        errors.append(f'{pfx}.text: quá dài (tối đa 200 ký tự).')


def _raise_if(errors: list[str]) -> None:
    if errors:
        raise ValidationError(errors)


# ── Helpers cho prompt builder ─────────────────────────────────────────────────

def build_spawn_points_table() -> str:
    lines = [
        "| background   | id              | x     | description                  |",
        "|--------------|-----------------|-------|------------------------------|",
    ]
    for bg, points in sorted(SPAWN_POINTS.items()):
        for p in points:
            lines.append(
                f"| {bg:<12} | {p['id']:<15} | {p['x']:.2f}  | {p['description']:<28} |"
            )
    return "\n".join(lines)


def build_bg_variants() -> str:
    return "\n".join(
        f"  {bg} ({', '.join(sorted(v))})"
        for bg, v in sorted(VALID_BACKGROUND_VARIANTS.items())
    )


def format_errors_for_retry(exc: ValidationError) -> str:
    lines = ["Fix these errors in your JSON:"]
    for i, e in enumerate(exc.errors, 1):
        lines.append(f"  [{i}] {e}")
    return "\n".join(lines)