# === src/core/scripts/pace.py ===
"""Pace profiles & scene parameter calculation.

Source-of-truth: ``target_seconds_per_scene`` + ``speed_rate``.
Word counts are DERIVED từ effective_wpm = TTS_WPM × speed_rate.

This module is PURE — no I/O, no engine dependency.
"""
from __future__ import annotations

import logging
from typing import Final, Self

from pydantic import BaseModel, Field, computed_field, model_validator

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# TTS CALIBRATION
# ─────────────────────────────────────────────────────────────────────────────
# TTS_WPM: tốc độ đọc cơ sở (raw) khi speed_rate=1.0.
# Đo thực tế bằng calibrate_tts.py với voice + speed=1.0.
TTS_WPM: Final[int] = 252

# Pace → speed_rate hợp lệ trong khoảng Vbee chấp nhận (0.1–1.9)
_MIN_SPEED_RATE: Final[float] = 0.1
_MAX_SPEED_RATE: Final[float] = 1.9

type PaceKey = str
DEFAULT_PACE: Final[PaceKey] = "balanced"

_DURATION_DRIFT_TOLERANCE: Final[float] = 0.05


# ─────────────────────────────────────────────────────────────────────────────
# PaceProfile
# ─────────────────────────────────────────────────────────────────────────────

class PaceProfile(BaseModel):
    """Configuration for one pacing style.

    Math contract (validated at construction):
        effective_wpm   = TTS_WPM × speed_rate
        words_per_scene = round(target_seconds_per_scene × effective_wpm / 60)

    speed_rate < 1.0 → đọc chậm → cùng duration cần ÍT từ hơn
    speed_rate > 1.0 → đọc nhanh → cùng duration cần NHIỀU từ hơn

    Attributes:
        target_seconds_per_scene: Thời lượng cảnh lý tưởng. PRIMARY input.
        min_seconds_per_scene:    Sàn duration sau clamp.
        max_seconds_per_scene:    Trần duration sau clamp.
        min_scenes:               Số cảnh tối thiểu.
        speed_rate:               Vbee speed_rate (0.1–1.9). Cinematic chậm,
                                  fast_cut nhanh.
        description:              Human-readable label.
    """

    model_config = {"frozen": True}

    target_seconds_per_scene: float = Field(gt=0, le=30)
    min_seconds_per_scene:    float = Field(gt=0, le=30)
    max_seconds_per_scene:    float = Field(gt=0, le=30)
    min_scenes:               int   = Field(ge=1)
    speed_rate:               float = Field(ge=_MIN_SPEED_RATE, le=_MAX_SPEED_RATE)
    description:              str

    @model_validator(mode="after")
    def _validate_seconds_range(self) -> Self:
        """Đảm bảo min ≤ target ≤ max."""
        if not (self.min_seconds_per_scene
                <= self.target_seconds_per_scene
                <= self.max_seconds_per_scene):
            raise ValueError(
                f"Invalid pace profile: min={self.min_seconds_per_scene}s, "
                f"target={self.target_seconds_per_scene}s, "
                f"max={self.max_seconds_per_scene}s — must be monotonic."
            )
        return self

    # Derived properties ──────────────────────────────────────────────────────

    @computed_field  # type: ignore[prop-decorator]
    @property
    def effective_wpm(self) -> float:
        """Tốc độ đọc thực tế sau khi áp speed_rate.

        Stage 1 (Claude word count) PHẢI dùng giá trị này, không phải TTS_WPM raw.
        """
        return TTS_WPM * self.speed_rate

    @computed_field  # type: ignore[prop-decorator]
    @property
    def ideal_words_per_scene(self) -> int:
        return round(self.target_seconds_per_scene * self.effective_wpm / 60)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def min_words_per_scene(self) -> int:
        return round(self.min_seconds_per_scene * self.effective_wpm / 60)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def max_words_per_scene(self) -> int:
        return round(self.max_seconds_per_scene * self.effective_wpm / 60)


# ─────────────────────────────────────────────────────────────────────────────
# SceneParams — propagate speed_rate xuống Stage 3
# ─────────────────────────────────────────────────────────────────────────────

class SceneParams(BaseModel):
    """Computed scene parameters — Stage 1 ↔ Stage 3 ↔ Stage 4 contract.

    Attributes:
        total_words:               Tổng từ Claude phải sinh.
        num_scenes:                Số cảnh.
        words_per_scene:           Budget từ/cảnh.
        target_seconds_per_scene:  Hint duration cho Stage 4.
        max_seconds_per_scene:     Soft threshold cho Stage 4 detection.
        speed_rate:                Vbee speed_rate, propagate xuống Stage 3.
        pace_key:                  Tên profile để log/debug.
    """

    model_config = {"frozen": True}

    total_words:              int   = Field(gt=0)
    num_scenes:               int   = Field(gt=0)
    words_per_scene:          int   = Field(gt=0)
    target_seconds_per_scene: float = Field(gt=0)
    max_seconds_per_scene:    float = Field(gt=0)
    speed_rate:               float = Field(ge=_MIN_SPEED_RATE, le=_MAX_SPEED_RATE)
    pace_key:                 str

    @computed_field  # type: ignore[prop-decorator]
    @property
    def predicted_duration_seconds(self) -> float:
        return self.num_scenes * self.target_seconds_per_scene


# ─────────────────────────────────────────────────────────────────────────────
# Profile registry — speed_rate đã được nhúng vào mỗi profile
# ─────────────────────────────────────────────────────────────────────────────

PACE_PROFILES: Final[dict[PaceKey, PaceProfile]] = {
    # 2–3s / cảnh — Meme, drama, breaking news
    "fast_cut": PaceProfile(
        target_seconds_per_scene=2.5,
        min_seconds_per_scene=2.0,
        max_seconds_per_scene=3.5,
        min_scenes=8,
        speed_rate=1.3,                          # đọc nhanh
        description="Meme / trending / drama — 2–3s mỗi cảnh",
    ),
    # 4–5s / cảnh — Tin tức, top list, life tips
    "dynamic": PaceProfile(
        target_seconds_per_scene=4.5,
        min_seconds_per_scene=3.5,
        max_seconds_per_scene=5.5,
        min_scenes=6,
        speed_rate=1.15,                         # hơi nhanh
        description="Tin tức / list / trend — 4–5s mỗi cảnh",
    ),
    # 5–7s / cảnh — Default, explainer, how-to
    "balanced": PaceProfile(
        target_seconds_per_scene=6.0,
        min_seconds_per_scene=5.0,
        max_seconds_per_scene=7.5,
        min_scenes=4,
        speed_rate=1.0,                          # baseline
        description="Giáo dục / câu chuyện ngắn — 5–7s mỗi cảnh (default)",
    ),
    # 7–9s / cảnh — Storytelling, lịch sử, true crime
    "storytelling": PaceProfile(
        target_seconds_per_scene=8.0,
        min_seconds_per_scene=7.0,
        max_seconds_per_scene=10.0,
        min_scenes=4,
        speed_rate=0.9,                          # chậm rãi
        description="Kể chuyện / lịch sử / docs — 7–9s mỗi cảnh",
    ),
    # 9–12s / cảnh — Cinematic, philosophical, slow
    "cinematic": PaceProfile(
        target_seconds_per_scene=10.5,
        min_seconds_per_scene=9.0,
        max_seconds_per_scene=13.0,
        min_scenes=3,
        speed_rate=0.8,                          # chậm — lắng đọng
        description="Kể chuyện lắng đọng / sâu sắc — 9–12s mỗi cảnh",
    ),
}


def resolve_pace(pace: PaceKey | None) -> PaceProfile:
    """Tra cứu PaceProfile từ key, fallback về DEFAULT_PACE."""
    if pace is None:
        return PACE_PROFILES[DEFAULT_PACE]

    normalized = pace.strip().lower()
    resolved = PACE_PROFILES.get(normalized)
    if resolved is None:
        logger.warning(
            "pace.resolve.fallback",
            extra={"requested": pace, "fallback": DEFAULT_PACE},
        )
        return PACE_PROFILES[DEFAULT_PACE]
    return resolved


# ─────────────────────────────────────────────────────────────────────────────
# Calibration helper (giữ nguyên)
# ─────────────────────────────────────────────────────────────────────────────

def calibrate_tts_wpm(sample_text: str, actual_duration_sec: float) -> int:
    """Tính tts_wpm thực tế từ 1 đoạn text mẫu đã TTS xong.

    QUAN TRỌNG: phải đo với speed_rate=1.0 để có baseline TTS_WPM.
    """
    if not sample_text.strip():
        raise ValueError("sample_text không được rỗng")
    if actual_duration_sec <= 0:
        raise ValueError(f"actual_duration_sec phải > 0, got {actual_duration_sec}")

    word_count = len(sample_text.split())
    wpm = int(word_count / actual_duration_sec * 60)
    clamped = max(80, min(350, wpm))
    logger.info(
        "tts.calibrate",
        extra={
            "word_count":   word_count,
            "duration_sec": actual_duration_sec,
            "raw_wpm":      wpm,
            "clamped_wpm":  clamped,
        },
    )
    return clamped


# ─────────────────────────────────────────────────────────────────────────────
# Core calculation — KEY FIX: dùng effective_wpm
# ─────────────────────────────────────────────────────────────────────────────

def calc_scene_params(minutes: float, pace: PaceKey | None = None) -> SceneParams:
    """Tính scene params với detection cho duration không khả thi."""
    if minutes <= 0:
        raise ValueError(f"minutes must be positive, got {minutes}")

    profile = resolve_pace(pace)
    pace_key = (
        pace.strip().lower()
        if pace and pace.strip().lower() in PACE_PROFILES
        else DEFAULT_PACE
    )

    total_target_seconds = minutes * 60.0

    # ★ NEW: DETECTION sớm — duration quá ngắn cho profile
    min_feasible_duration = profile.min_seconds_per_scene * profile.min_scenes
    if total_target_seconds < min_feasible_duration:
        logger.warning(
            "pace.duration_too_short",
            extra={
                "pace":                  pace_key,
                "target_seconds":        total_target_seconds,
                "min_feasible_seconds":  min_feasible_duration,
                "min_seconds_per_scene": profile.min_seconds_per_scene,
                "min_scenes":            profile.min_scenes,
                "advice": (
                    f"Pace '{pace_key}' cần ÍT NHẤT {min_feasible_duration:.0f}s "
                    f"({profile.min_scenes} cảnh × {profile.min_seconds_per_scene}s). "
                    f"Video sẽ DÀI HƠN target {total_target_seconds:.0f}s. "
                    f"Suggest: dùng pace 'balanced' hoặc 'dynamic'."
                ),
            },
        )

    num_scenes = max(
        profile.min_scenes,
        round(total_target_seconds / profile.target_seconds_per_scene),
    )

    raw_sec_per_scene = total_target_seconds / num_scenes
    actual_sec_per_scene = min(
        profile.max_seconds_per_scene,
        max(profile.min_seconds_per_scene, raw_sec_per_scene),
    )

    effective_wpm = profile.effective_wpm
    words_per_scene = round(actual_sec_per_scene * effective_wpm / 60)
    total_words = words_per_scene * num_scenes

    predicted_duration = num_scenes * actual_sec_per_scene
    drift = abs(predicted_duration - total_target_seconds) / total_target_seconds
    if drift > _DURATION_DRIFT_TOLERANCE:
        logger.warning(
            "scene_params.duration_drift",
            extra={
                "pace":              pace_key,
                "minutes":           minutes,
                "target_seconds":    total_target_seconds,
                "predicted_seconds": predicted_duration,
                "drift_pct":         round(drift * 100, 2),
                "num_scenes":        num_scenes,
                "speed_rate":        profile.speed_rate,
                "effective_wpm":     round(effective_wpm, 1),
            },
        )

    return SceneParams(
        total_words=total_words,
        num_scenes=num_scenes,
        words_per_scene=words_per_scene,
        target_seconds_per_scene=actual_sec_per_scene,
        max_seconds_per_scene=profile.max_seconds_per_scene,
        speed_rate=profile.speed_rate,
        pace_key=pace_key,
    )