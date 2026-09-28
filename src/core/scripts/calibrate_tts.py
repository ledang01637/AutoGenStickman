# === src.core.scripts.calibrate_tts.py ===
"""calibrate_tts.py — Đo TTS_WPM thực tế của Vbee voice và update pace.py.

CALIBRATION GIẢI THÍCH:
  - WPM (words per minute) = tốc độ đọc thực tế của TTS engine.
  - Code dùng `TTS_WPM` để tính số từ Claude phải sinh cho mỗi scene.
  - Nếu `TTS_WPM` sai → audio dài/ngắn hơn target → video bị drift.

CHIẾN LƯỢC:
  1. Synthesize 3 samples với độ dài khác nhau ở speed_rate=1.0 (BASELINE).
  2. Đo duration thật từ MP3 metadata.
  3. Tính avg WPM = total_words / total_duration × 60.
  4. (Optional) Update TTS_WPM trong pace.py qua regex + backup.

CHẠY:
    python scripts/calibrate_tts.py                    # dry-run, in WPM
    python scripts/calibrate_tts.py --save             # ghi đè pace.py
    python scripts/calibrate_tts.py --voice <code>     # voice khác

YÊU CẦU:
    - VBEE_API_KEY + VBEE_APP_ID đã set trong env
    - moviepy installed (đã có sẵn cho video_engine)
"""
from __future__ import annotations

import argparse
import asyncio
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# ── Đảm bảo import hoạt động khi chạy trực tiếp ─────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from moviepy import AudioFileClip  # noqa: E402

from src.core.voice.vbee_engine import VbeeEngine  # noqa: E402
import src.core.scripts.pace as _pace_module  # noqa: E402

PACE_PATH = Path(_pace_module.__file__).resolve()


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_VOICE_CODE = "hn_female_ngochuyen_full_48k-fhg"

# 3 samples độ dài tăng dần — average sẽ chính xác hơn 1 sample lẻ.
# Số từ = len(text.split()) — verify lại bằng manual count nếu nghi ngờ.
SAMPLES: list[str] = [
    # ~22 từ
    "Hôm nay trời đẹp tuyệt vời. Tôi đi bộ ra công viên gần nhà. "
    "Có rất nhiều người đang tập thể dục.",

    # ~27 từ
    "Khoa học đã chứng minh rằng giấc ngủ rất quan trọng cho sức khỏe não bộ "
    "con người. Mỗi ngày chúng ta cần ngủ đủ tám tiếng để hoạt động tốt.",

    # ~35 từ
    "Trong lịch sử thế giới, có rất nhiều câu chuyện thú vị về các vị vua thời "
    "xưa. Họ thường có cuộc sống vô cùng xa hoa và quyền lực. Nhưng đằng sau "
    "đó cũng đầy bí ẩn.",
]

OUTPUT_DIR = Path("temp_calibrate")

# Regex match dòng `TTS_WPM: Final[int] = 275` (linh hoạt với annotation)
TTS_WPM_RE = re.compile(
    r"^(?P<prefix>TTS_WPM(?:\s*:\s*Final\[int\]|\s*:\s*int)?\s*=\s*)"
    r"(?P<old>\d+)"
    r"(?P<tail>\s*(?:#.*)?)$",
    flags=re.MULTILINE,
)


# ─────────────────────────────────────────────────────────────────────────────
# DATA CLASSES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SampleResult:
    """Kết quả đo 1 sample."""
    text:        str
    word_count:  int
    duration_s:  float
    wpm:         float


# ─────────────────────────────────────────────────────────────────────────────
# CALIBRATION
# ─────────────────────────────────────────────────────────────────────────────

async def calibrate(voice_code: str) -> int | None:
    """Đo WPM thực tế của Vbee voice ở speed_rate=1.0.

    Args:
        voice_code: Voice của Vbee (vd ``"hn_female_ngochuyen_full_48k-fhg"``).

    Returns:
        WPM trung bình (int) hoặc None nếu lỗi.
    """
    OUTPUT_DIR.mkdir(exist_ok=True)
    results: list[SampleResult] = []

    print(f"\n🎙  Vbee Calibration — voice: {voice_code}")
    print(f"    speed_rate = 1.0 (BASELINE)\n")

    # ★ speed_rate=1.0 BẮT BUỘC để có baseline đúng
    async with VbeeEngine(voice_code=voice_code, speed_rate=1.0) as engine:
        if not await engine.health_check():
            print("❌ Vbee health check failed — kiểm tra VBEE_API_KEY/VBEE_APP_ID")
            return None

        for i, text in enumerate(SAMPLES, 1):
            word_count = len(text.split())
            mp3_path = OUTPUT_DIR / f"sample_{i}.mp3"

            print(f"  [{i}/{len(SAMPLES)}] Synthesize {word_count} từ...", end=" ", flush=True)
            result = await engine.generate_voice(text=text, output_path=mp3_path)

            if not result.success:
                print(f"❌ {result.error}")
                continue

            try:
                audio = AudioFileClip(str(mp3_path))
                duration = audio.duration
                audio.close()
            except Exception as exc:
                print(f"❌ Không đọc được MP3: {exc}")
                continue

            wpm = word_count / duration * 60
            results.append(SampleResult(
                text=text,
                word_count=word_count,
                duration_s=duration,
                wpm=wpm,
            ))
            print(f"✓ {duration:.2f}s → {wpm:.0f} WPM")

    if not results:
        print("\n❌ Không có sample nào thành công.")
        return None

    # Aggregate — tính theo tổng (weighted by duration), không phải mean(wpm)
    total_words = sum(r.word_count for r in results)
    total_duration = sum(r.duration_s for r in results)
    avg_wpm = total_words / total_duration * 60

    # Print summary
    print("\n" + "═" * 60)
    print("  KẾT QUẢ CALIBRATION")
    print("═" * 60)
    print(f"  Total: {total_words} từ / {total_duration:.2f}s")
    print(f"  📊 AVG WPM = {avg_wpm:.0f}")

    # So với hiện tại
    current_wpm = _pace_module.TTS_WPM
    diff_pct = (avg_wpm - current_wpm) / current_wpm * 100
    print(f"\n  Code đang dùng TTS_WPM = {current_wpm}")
    print(f"  Diff: {diff_pct:+.1f}%")

    if abs(diff_pct) > 10:
        print("  ⚠  Diff > 10% — RECOMMEND update")
    elif abs(diff_pct) > 5:
        print("  ⚠  Diff 5-10% — có thể update")
    else:
        print("  ✓  Diff < 5% — OK, không cần update")

    print("═" * 60)
    return round(avg_wpm)


# ─────────────────────────────────────────────────────────────────────────────
# AUTO-UPDATE pace.py
# ─────────────────────────────────────────────────────────────────────────────

def update_pace_file(new_wpm: int, dry_run: bool = True) -> bool:
    """Update TTS_WPM trong src/domain/pace.py.

    Args:
        new_wpm: Giá trị WPM mới.
        dry_run: True → chỉ in diff, không ghi.

    Returns:
        True nếu thành công (hoặc dry-run completed), False nếu lỗi.
    """
    if not PACE_PATH.exists():
        print(f"\n❌ Không tìm thấy {PACE_PATH}")
        return False

    source = PACE_PATH.read_text(encoding="utf-8")
    matches = list(TTS_WPM_RE.finditer(source))

    if not matches:
        print(f"\n❌ Không tìm thấy dòng `TTS_WPM = N` trong {PACE_PATH.name}")
        print("    File có thể đã bị đổi format. Update manually.")
        return False

    if len(matches) > 1:
        print(f"\n⚠  Tìm thấy {len(matches)} dòng TTS_WPM — chỉ nên có 1!")
        return False

    match = matches[0]
    old_wpm = int(match.group("old"))

    if old_wpm == new_wpm:
        print(f"\n✓ TTS_WPM đã = {new_wpm} rồi — không cần update.")
        return True

    new_source = TTS_WPM_RE.sub(
        lambda m: f"{m.group('prefix')}{new_wpm}{m.group('tail')}",
        source,
    )

    # In diff
    print(f"\n  📝 THAY ĐỔI TRONG {PACE_PATH.name}:")
    print("  " + "─" * 56)
    for old_line, new_line in zip(source.splitlines(), new_source.splitlines()):
        if old_line != new_line:
            print(f"  - {old_line}")
            print(f"  + {new_line}")
    print("  " + "─" * 56)

    if dry_run:
        print("\n  ℹ  DRY-RUN — chạy lại với --save để ghi thật.")
        return True

    # Backup + write
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = PACE_PATH.with_suffix(f".py.bak_{timestamp}")
    shutil.copy2(PACE_PATH, backup_path)
    print(f"  ✓ Backup → {backup_path.name}")

    PACE_PATH.write_text(new_source, encoding="utf-8")
    print(f"  ✓ Đã update TTS_WPM={new_wpm} trong {PACE_PATH.name}")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

async def main(voice_code: str, save: bool) -> None:
    avg_wpm = await calibrate(voice_code)

    if avg_wpm is None:
        sys.exit(1)

    print(f"\n  → Đề xuất: TTS_WPM = {avg_wpm}")
    update_pace_file(avg_wpm, dry_run=not save)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Đo TTS_WPM thực tế của Vbee và update pace.py.",
    )
    parser.add_argument(
        "--voice",
        type=str,
        default=DEFAULT_VOICE_CODE,
        help=f"Vbee voice_code (default: {DEFAULT_VOICE_CODE})",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Ghi đè TTS_WPM vào src/domain/pace.py (có backup auto). "
             "Nếu không có cờ này, chỉ dry-run.",
    )
    args = parser.parse_args()
    asyncio.run(main(voice_code=args.voice, save=args.save))