# src/utils/scene_naming.py
"""
Scene naming utilities — chuẩn hoá scene_id thành filename index.

Dùng chung giữa BaseImageEngine và worker để đảm bảo image/audio cùng
naming convention: "s1" → "scene_001.png" / "scene_001.mp3".
"""

import re

# Regex tách số cuối từ scene_id bất kể format:
# "s1" → "1" | "scene_01" → "01" | "act_03" → "03" | "12" → "12"
_SCENE_ID_NUMBER_RE = re.compile(r"(\d+)$")


def scene_filename_index(scene_id: str) -> str:
    """Chuẩn hoá scene_id thành chuỗi số zero-padded 3 chữ số.

    BUG FIX: scene_id dạng "scene_01" khiến zfill() trả nguyên chuỗi
    → filename bị "scene_scene_01.png". Hàm này extract số cuối từ
    scene_id trước khi zero-pad, đảm bảo output luôn là "001".

    Examples:
        "s1"       → "001"
        "scene_03" → "003"
        "12"       → "012"
        "act_007"  → "007"
        "xyz"      → "xyz"  (fallback nếu không tìm thấy số)

    Args:
        scene_id: ID cảnh — bất kể format.

    Returns:
        Chuỗi 3 ký tự số (zero-padded) hoặc nguyên scene_id nếu không có số.
    """
    match = _SCENE_ID_NUMBER_RE.search(str(scene_id))
    return match.group(1).zfill(3) if match else str(scene_id)