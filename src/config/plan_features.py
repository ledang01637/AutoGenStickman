# src/config/plan_features.py

from enum import Enum
from dataclasses import dataclass
from typing import Optional
from fastapi import HTTPException, status
from ..core.database.schemas import VideoProjectCreate


class PlanTier(str, Enum):
    FREE  = "Free"
    BASIC = "Basic"
    TRIAL = "Trial"
    PRO   = "Pro"
    ULTRA = "Ultra"


class AllowedPace(str, Enum):
    BALANCED     = "balanced"
    DYNAMIC      = "dynamic"
    STORYTELLING = "storytelling"
    FAST_CUT     = "fast_cut"
    CINEMATIC    = "cinematic"


class AllowedTone(str, Enum):
    SERIOUS      = "serious"
    STORYTELLING = "storytelling"
    MOTIVATIONAL = "motivational"
    GENZ_MEME    = "genz_meme"
    DARK_HUMOR   = "dark_humor"


class AllowedStoryStructure(str, Enum):
    PROBLEM_SOLVE   = "problem_solve"
    RANKING         = "ranking"
    TIMELINE        = "timeline"
    HERO_JOURNEY    = "hero_journey"
    MYTH_BUSTING    = "myth_busting"
    BEFORE_AFTER    = "before_after"
    HOOK_TWIST      = "hook_twist"
    DEBATE          = "debate"
    RAGS_TO_RICHES  = "rags_to_riches"
    POV             = "pov"
    WHAT_IF         = "what_if"
    FALL_FROM_GRACE = "fall_from_grace"
    MYSTERY_REVEAL  = "mystery_reveal"
    ICEBERG         = "iceberg"

class AllowedVoice(str, Enum):
    # Miền Bắc
    HN_FEMALE_NGOCHUYEN  = "hn_female_ngochuyen_full_48k-fhg"
    HN_MALE_MANHDUNG     = "hn_male_manhdung_news_48k-fhg"
    # Miền Trung
    HUE_FEMALE_HUONGGIANG = "hue_female_huonggiang_full_48k-fhg"
    HUE_MALE_DUYPHUONG   = "hue_male_duyphuong_full_48k-fhg"
    # Miền Nam
    SG_FEMALE_LANTRINH   = "sg_female_lantrinh_vdts_48k-fhg"
    SG_MALE_TRUNGKIEN    = "sg_male_trungkien_vdts_48k-fhg"
    # Đặc biệt
    HN_MALE_PHUTHANG_STOR = "hn_male_phuthang_stor80dt_48k-fhg"   # Đọc chuyện
    HN_MALE_PHUTHANG_NEWS = "hn_male_phuthang_news65dt_44k-fhg"   # Tin tức

class AllowedLanguage(str, Enum):
    VI    = "vi"
    EN    = "en"
    VI_EN = "vi_en"


class ClaudeModel(str, Enum):
    FAST     = "claude-haiku-4-5-20251001"
    BALANCED = "claude-sonnet-4-6"
    BEST     = "claude-opus-4-7"


@dataclass(frozen=True)
class PlanFeatureConfig:
    max_minutes:             float
    allowed_paces:           frozenset[str]
    allowed_tones:           Optional[frozenset[str]]   # None = tất cả
    allowed_structures:      Optional[frozenset[str]]   # None = tất cả
    allowed_languages:       frozenset[str]
    allowed_voices:          Optional[frozenset[str]]
    claude_model:            str
    default_pace:            str = "balanced"
    default_structure:       str = "problem_solve"
    default_tone:            str = "serious"
    default_voice:           str = "hn_female_ngochuyen_full_48k-fhg"
    max_credits_per_video:   int = 10

_FREE_VOICES = frozenset([
    AllowedVoice.HN_FEMALE_NGOCHUYEN,                 
])

_BASIC_VOICES = frozenset([
    AllowedVoice.HN_FEMALE_NGOCHUYEN,
    AllowedVoice.HN_MALE_MANHDUNG,
    AllowedVoice.SG_FEMALE_LANTRINH,               
])

_ALL_VOICES = frozenset([v.value for v in AllowedVoice])  


PLAN_FEATURES: dict[str, PlanFeatureConfig] = {

    # ── FREE ─────────────────────────────────────────────────────
    # Cho dùng dynamic để tạo Aha Moment, nhưng giới hạn 45 giây
    # Tone: chỉ serious — ít rủi ro AI output xấu
    # Structure: chỉ 2 cái cơ bản nhất
    PlanTier.FREE: PlanFeatureConfig(
        max_minutes           = 0.5,
        allowed_paces         = frozenset(["balanced", "dynamic"]),
        allowed_tones         = frozenset(["serious"]),
        allowed_structures    = frozenset(["problem_solve", "ranking"]),
        allowed_languages     = frozenset(["vi"]),
        allowed_voices        = _FREE_VOICES,
        claude_model          = ClaudeModel.FAST,
        default_pace          = "dynamic",
        default_structure     = "problem_solve",
        default_tone          = "serious",
        default_voice         = AllowedVoice.HN_FEMALE_NGOCHUYEN,
        max_credits_per_video = 4,
    ),

    # ── BASIC ────────────────────────────────────────────────────
    # Mở storytelling pace + before_after (chốt sale affiliate)
    # Tone: thêm storytelling + motivational (kênh quote/podcast)
    PlanTier.BASIC: PlanFeatureConfig(
        max_minutes           = 1,
        allowed_paces         = frozenset(["balanced", "dynamic", "storytelling"]),
        allowed_tones         = frozenset(["serious", "storytelling", "motivational"]),
        allowed_structures    = frozenset([
            "problem_solve", "ranking",
            "timeline", "hero_journey", "myth_busting", "before_after",
        ]),
        allowed_voices        = _BASIC_VOICES,
        allowed_languages     = frozenset(["vi"]),
        claude_model          = ClaudeModel.FAST,
        default_pace          = "balanced",
        default_structure     = "problem_solve",
        default_tone          = "serious",
        default_voice         = AllowedVoice.HN_FEMALE_NGOCHUYEN,
        max_credits_per_video = 12,
    ),

    # ── TRIAL ────────────────────────────────────────────────────
    # Tương đương Pro nhưng không có vi_en, dùng để thử trước khi mua Pro
    PlanTier.TRIAL: PlanFeatureConfig(
        max_minutes           = 3.0,
        allowed_paces         = frozenset(["balanced", "dynamic", "storytelling", "fast_cut"]),
        allowed_tones         = frozenset(["serious", "storytelling", "motivational", "genz_meme"]),
        allowed_structures    = frozenset([
            "problem_solve", "ranking",
            "timeline", "hero_journey", "myth_busting", "before_after",
            "hook_twist", "debate", "rags_to_riches", "pov", "what_if",
        ]),
        allowed_voices        = _ALL_VOICES, 
        allowed_languages     = frozenset(["vi", "en"]),
        claude_model          = ClaudeModel.BALANCED,
        default_pace          = "balanced",
        default_structure     = "problem_solve",
        default_tone          = "serious",
        default_voice         = AllowedVoice.HN_FEMALE_NGOCHUYEN,
        max_credits_per_video = 30,
    ),

    # ── PRO ──────────────────────────────────────────────────────
    # Fast Cut là key selling point
    # Gen Z Meme mở ở Pro — AI viết không bị "đơ" là differentiator thật
    # Rags to Riches: ngôn ngữ tài chính, RPM cao
    PlanTier.PRO: PlanFeatureConfig(
        max_minutes           = 3.0,
        allowed_paces         = frozenset(["balanced", "dynamic", "storytelling", "fast_cut"]),
        allowed_tones         = frozenset(["serious", "storytelling", "motivational", "genz_meme"]),
        allowed_structures    = frozenset([
            "problem_solve", "ranking",
            "timeline", "hero_journey", "myth_busting", "before_after",
            "hook_twist", "debate", "rags_to_riches", "pov", "what_if",
        ]),
        allowed_voices        = _ALL_VOICES, 
        allowed_languages     = frozenset(["vi", "en", "vi_en"]),
        claude_model          = ClaudeModel.BALANCED,
        default_pace          = "balanced",
        default_structure     = "problem_solve",
        default_tone          = "serious",
        max_credits_per_video = 30,
    ),

    # ── ULTRA ────────────────────────────────────────────────────
    # Cinematic: YouTube dài, render nặng, context lớn
    # Dark Humor: fine-tune tốn kém + risk policy cao → Ultra accountability
    # Fall/Mystery/Iceberg: True Crime, documentary, RPM khổng lồ
    PlanTier.ULTRA: PlanFeatureConfig(
        max_minutes           = 5.0,
        allowed_paces         = frozenset(["balanced", "dynamic", "storytelling", "fast_cut", "cinematic"]),
        allowed_tones         = None,  # tất cả bao gồm dark_humor
        allowed_structures    = None,  # tất cả bao gồm fall_from_grace, mystery_reveal, iceberg
        allowed_languages     = frozenset(["vi", "en", "vi_en"]),
        allowed_voices        = None,  # tất cả
        claude_model          = ClaudeModel.BALANCED,
        default_pace          = "balanced",
        default_structure     = "problem_solve",
        default_tone          = "serious",
        default_voice         = AllowedVoice.HN_FEMALE_NGOCHUYEN,
        max_credits_per_video = 200,
    ),
}


class PlanFeatureValidator:

    def __init__(self, plan_name: str):
        tier = (
            PlanTier(plan_name)
            if plan_name in PlanTier._value2member_map_
            else PlanTier.FREE
        )
        self.config = PLAN_FEATURES[tier]
        self.tier   = tier

    def validate(self, project_in: "VideoProjectCreate") -> None:
        cfg    = self.config
        errors: list[str] = []

        # 1. Thời lượng
        if project_in.minutes > cfg.max_minutes:
            errors.append(
                f"Gói {self.tier.value} chỉ cho phép tối đa {cfg.max_minutes} phút "
                f"(bạn gửi {project_in.minutes} phút)."
            )

        # 2. Pace
        if project_in.pace and project_in.pace not in cfg.allowed_paces:
            errors.append(
                f"Pace '{project_in.pace}' không khả dụng ở gói {self.tier.value}. "
                f"Được phép: {', '.join(sorted(cfg.allowed_paces))}."
            )

        # 3. Tone
        if cfg.allowed_tones is not None and project_in.tone not in cfg.allowed_tones:
            errors.append(
                f"Tone '{project_in.tone}' không khả dụng ở gói {self.tier.value}. "
                f"Được phép: {', '.join(sorted(cfg.allowed_tones))}."
            )

        # 4. Story structure — check từng giá trị cụ thể
        if (
            project_in.story_structure
            and cfg.allowed_structures is not None
            and project_in.story_structure not in cfg.allowed_structures
        ):
            errors.append(
                f"Story structure '{project_in.story_structure}' không khả dụng "
                f"ở gói {self.tier.value}."
            )

        # 5. Ngôn ngữ
        if project_in.language and project_in.language not in cfg.allowed_languages:
            errors.append(
                f"Ngôn ngữ '{project_in.language}' chưa hỗ trợ ở gói {self.tier.value}."
            )

        # 6. Voice
        if (
            project_in.voice_code
            and cfg.allowed_voices is not None
            and project_in.voice_code not in cfg.allowed_voices
        ):
            errors.append(
                f"Giọng đọc '{project_in.voice_code}' không khả dụng ở gói {self.tier.value}. "
                f"Nâng cấp lên Pro để dùng tất cả giọng đọc."
            )

        if errors:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "message": "Tính năng không khả dụng ở gói hiện tại.",
                    "errors":  errors,
                    "current_plan": self.tier.value,
                    "upgrade_hint": _upgrade_hint(self.tier),
                },
            )

    def apply_defaults(self, project_in: "VideoProjectCreate") -> "VideoProjectCreate":
        """Silent fallback — override về giá trị an toàn thay vì raise lỗi."""
        cfg     = self.config
        updates = {}

        if project_in.minutes > cfg.max_minutes:
            updates["minutes"] = cfg.max_minutes

        if project_in.pace not in cfg.allowed_paces:
            updates["pace"] = cfg.default_pace

        if cfg.allowed_tones is not None and project_in.tone not in cfg.allowed_tones:
            updates["tone"] = cfg.default_tone

        if (
            project_in.story_structure
            and cfg.allowed_structures is not None
            and project_in.story_structure not in cfg.allowed_structures
        ):
            updates["story_structure"] = cfg.default_structure

        if (
            project_in.voice_code
            and cfg.allowed_voices is not None
            and project_in.voice_code not in cfg.allowed_voices
        ):
            updates["voice_code"] = cfg.default_voice

        if updates:
            project_in = project_in.model_copy(update=updates)

        return project_in

    @property
    def model(self) -> str:
        """Model AI thực tế dùng để generate — có thể override bởi use_best_model."""
        return self.config.claude_model


def _upgrade_hint(tier: PlanTier) -> str:
    return {
        PlanTier.FREE:  "Nâng lên Basic để mở thêm tính năng mới.",
        PlanTier.BASIC: "Nâng lên Pro để mở thêm tính năng mới.",
        PlanTier.TRIAL: "Nâng lên Pro để mở thêm tính năng mới.",
        PlanTier.PRO:   "Nâng lên Ultra để mở thêm tính năng mới.",
        PlanTier.ULTRA: "Bạn đang dùng gói cao nhất.",
    }.get(tier, "")