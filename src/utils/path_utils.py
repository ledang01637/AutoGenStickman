# === src/utils/path_utils.py ===
"""Path utilities — đảm bảo persistence path luôn absolute.

Lý do: Worker có thể chạy từ cwd khác (systemd service, K8s pod). Nếu DB
lưu relative path, Stage 4 query lại sẽ resolve theo cwd hiện tại → fail.
"""
from __future__ import annotations

from pathlib import Path


def to_absolute_path(p: str | Path) -> str:
    """Convert path → absolute POSIX string.

    Args:
        p: Path tương đối hoặc tuyệt đối.

    Returns:
        Absolute path dạng POSIX (forward slash trên cả Win/Unix).
        Trả "" nếu input rỗng.
    """
    if not p:
        return ""
    return Path(p).resolve().as_posix()


def safe_resolve(p: str | Path) -> str:
    """Resolve path không raise (cho logging).

    Trả về raw path nếu resolve fail (path invalid trên OS hiện tại).
    """
    if not p:
        return "<empty>"
    try:
        return Path(p).resolve().as_posix()
    except (OSError, RuntimeError):
        return f"<unresolvable:{p}>"


def safe_exists(p: str | Path) -> bool:
    """Check exists không raise (cho logging/filter)."""
    if not p:
        return False
    try:
        return Path(p).exists()
    except (OSError, ValueError):
        return False