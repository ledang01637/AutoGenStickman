# === src/core/utils/voiceover_trimmer.py ===
"""Trim filler words trong voiceover tiếng Việt để fit word cap.

Pure function — no I/O, deterministic.

Strategy:
    1. Tokenize bằng split() (đủ cho Vietnamese).
    2. Loại bỏ filler words theo priority order (cắt từ ít quan trọng nhất).
    3. Stop khi đạt target hoặc hết filler.

KHÔNG cố trim quá deep — nếu cần cắt > 20% → caller nên retry Claude.
"""
from __future__ import annotations

import logging
import re
from typing import Final

logger = logging.getLogger(__name__)


# Filler words tiếng Việt — sắp xếp theo PRIORITY (cắt cái đầu tiên trước).
# Mỗi tuple: (filler_word, có_thể_cắt_kèm_dấu_câu_trước)
#
# CHIẾN LƯỢC:
#   - Tier 1: Trạng từ tăng cường — cắt an toàn nhất, không đổi nghĩa.
#   - Tier 2: Trợ từ thái độ — cắt được, mất chút sắc thái nhưng OK.
#   - Tier 3: Bổ trợ thì — chỉ cắt khi context rõ.
#   - Tier 4: Liên từ — cắt cuối cùng, có thể đổi cấu trúc câu.
_FILLER_WORDS: Final[tuple[str, ...]] = (
    # Tier 1 — Trạng từ tăng cường (hoàn toàn an toàn)
    "vô cùng", "cực kỳ", "hết sức", "rất là",
    "thật sự", "thực sự", "thật là",

    # Tier 2 — Trợ từ thái độ
    "rồi đó", "đó nha", "đó mà",
    "rồi", "nhé", "nha", "đó", "ấy",

    # Tier 3 — Bổ trợ thì (cắt khi rõ context)
    "đã từng", "đang dần", "vẫn còn",

    # Tier 4 — Liên từ phụ thuộc (cắt cuối cùng)
    "rằng",
)

# Pattern khoảng trắng dư thừa sau khi cắt
_EXTRA_SPACE_RE: Final[re.Pattern[str]] = re.compile(r"\s+")
_SPACE_BEFORE_PUNCT_RE: Final[re.Pattern[str]] = re.compile(r"\s+([,.!?;:])")


def count_words(text: str) -> int:
    """Đếm từ tiếng Việt theo whitespace split."""
    return len(text.split())


def trim_to_word_cap(
    text:        str,
    target_words: int,
    max_trim_pct: float = 0.20,
) -> tuple[str, dict]:
    """Trim filler words để fit target_words.

    KHÔNG cắt nội dung quan trọng — chỉ filler. Nếu không thể fit cap
    chỉ với filler trim → trả về best-effort + flag ``need_retry=True``
    để caller quyết định retry Claude.

    Args:
        text:         Voiceover gốc.
        target_words: Số từ mục tiêu (cap).
        max_trim_pct: % tối đa được phép cắt. Vượt → fail soft.

    Returns:
        (trimmed_text, info_dict) với info:
            - original_words:   Số từ ban đầu.
            - final_words:      Số từ sau trim.
            - trimmed_words:    Số từ đã cắt.
            - trim_pct:         % cắt.
            - within_cap:       True nếu fit cap.
            - need_retry:       True nếu trim không đủ.

    Examples:
        >>> result, info = trim_to_word_cap(
        ...     "Hàng triệu người vô cùng chờ đợi rằng ngày thống nhất",
        ...     target_words=8,
        ... )
        >>> print(result)
        "Hàng triệu người chờ đợi ngày thống nhất"
    """
    original_words = count_words(text)

    if original_words <= target_words:
        return text, {
            "original_words": original_words,
            "final_words":    original_words,
            "trimmed_words":  0,
            "trim_pct":       0.0,
            "within_cap":     True,
            "need_retry":     False,
        }

    # Trim cần thiết
    excess = original_words - target_words
    max_trimmable = int(original_words * max_trim_pct)

    current = text
    trimmed_count = 0

    for filler in _FILLER_WORDS:
        if trimmed_count >= excess:
            break
        if trimmed_count >= max_trimmable:
            break

        # Pattern: " filler " hoặc " filler[.,!?]"
        # Word boundary cho Vietnamese tricky vì có dấu — dùng lookahead/lookbehind
        # với whitespace/punct.
        # Case-insensitive cho linh hoạt nếu Claude viết hoa filler.
        pattern = re.compile(
            rf"(\s){re.escape(filler)}(?=\s|[.,!?;:])",
            flags=re.IGNORECASE,
        )

        # Cắt từng instance MỘT MỘT để control overshoot
        while trimmed_count < excess and trimmed_count < max_trimmable:
            new_text, n_subs = pattern.subn("", current, count=1)
            if n_subs == 0:
                break  # Filler này đã hết
            words_removed = len(filler.split())
            trimmed_count += words_removed
            current = new_text

    # Cleanup: khoảng trắng dư + space trước dấu câu
    current = _EXTRA_SPACE_RE.sub(" ", current).strip()
    current = _SPACE_BEFORE_PUNCT_RE.sub(r"\1", current)

    final_words = count_words(current)
    within_cap = final_words <= target_words
    need_retry = not within_cap

    info = {
        "original_words": original_words,
        "final_words":    final_words,
        "trimmed_words":  original_words - final_words,
        "trim_pct":       round((original_words - final_words) / original_words * 100, 1),
        "within_cap":     within_cap,
        "need_retry":     need_retry,
    }

    if need_retry:
        logger.warning(
            "voiceover_trim.insufficient",
            extra={"target": target_words, **info},
        )
    else:
        logger.info(
            "voiceover_trim.ok",
            extra={"target": target_words, **info},
        )

    return current, info