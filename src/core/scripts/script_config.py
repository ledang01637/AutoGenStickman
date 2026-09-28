# === src/core/scripts/script_config.py ===
"""Configuration & preset registries cho script generation."""
from __future__ import annotations

from enum import Enum
from typing import Final

from pydantic import BaseModel, Field

from .pace import PaceProfile, SceneParams


MAIN_CHARACTER: Final[str] = "a stickman wearing a tie and round glasses"

STORY_STRUCTURES: Final[dict[str, str]] = {
    "hook_twist":      "Hook → Context → Escalation → Unexpected twist → Punchline",
    "problem_solve":   "Shocking problem → Root cause → Real consequences → Solution → Lesson",
    "timeline":        "Before it happened → Trigger event → Climax → Aftermath → Present day",
    "debate":          "Viewpoint A → Evidence A → Viewpoint B → Evidence B → Final verdict",
    "hero_journey":    "Ordinary life → Inciting incident → Trials & stumbles → Triumph → Hard-won lesson",
    "rags_to_riches":  "Rough start → Decision to change → Grueling journey → Turning point → Success",
    "fall_from_grace": "Peak glory → Cracks appear → Collapse → True cause → Lingering consequences",
    "mystery_reveal":  "Mysterious question → Clue 1 → Clue 2 → False theory → Shocking truth",
    "myth_busting":    "Common belief → Why people believe it → Counter-evidence → Actual truth → Practical takeaway",
    "ranking":         "List intro → Lowest rank → Middle ranks → Surprising high rank → Controversial #1",
    "iceberg":         "Surface everyone knows → Deeper layer → Deeper still → Hidden layer → Dark shocking bottom",
    "pov":             "Familiar setup → Unexpected POV twist → Comedic escalation → Climax → Final punchline",
    "before_after":    "Before knowing → Moment of realization → After knowing → Behavior change → Advice for newcomers",
    "what_if":         "What-if question → Scenario 1 → Scenario 2 → Domino consequences → Haunting conclusion",
}

TONE_PRESETS: Final[dict[str, str]] = {
    "genz_meme":    "Humorous, lightly sarcastic, fast-paced, Gen Z meme elements, trendy vocabulary",
    "serious":      "Serious, informative, objective, moderate pace, in-depth journalistic style",
    "storytelling": "Engaging narrative, emotional, step-by-step lead-in, builds empathy, narrative style",
    "dark_humor":   "Dark humor, cutting sarcasm, social commentary, unafraid to speak bluntly",
    "motivational": "Motivating, positive, high-energy, enthusiastic phrasing, strong call-to-action",
}

LANGUAGE_PRESETS: Final[dict[str, str]] = {
    "vi":    "Vietnamese",
    "en":    "English",
    "vi_en": "Vietnamese with English key terms in parentheses",
}

# Model IDs Anthropic (cập nhật 4/2026)
CLAUDE_MODELS: Final[dict[str, str]] = {
    # "fast":     "claude-haiku-4-5-20251001",
    "balanced": "claude-sonnet-4-6",
}

class TargetPlatform(str, Enum):
    TIKTOK   = "tiktok"
    REELS    = "reels"
    YOUTUBE  = "youtube"
    SHORTS   = "shorts"

def resolve_tone(tone: str) -> str:
    return TONE_PRESETS.get(tone.strip().lower(), tone.strip())


def resolve_language(language: str) -> str:
    return LANGUAGE_PRESETS.get(language.strip().lower(), language.strip())


def resolve_story_structure(structure: str) -> str:
    return STORY_STRUCTURES.get(structure.strip().lower(), structure.strip())


class ScriptGenConfig(BaseModel):
    """Cấu hình đầy đủ cho 1 lần sinh kịch bản.

    Immutable — tạo trong ``_build_script_config()``, không mutate sau đó.
    Không chứa state nào của engine instance → thread-safe.
    """

    model_config = {"frozen": True, "arbitrary_types_allowed": True}

    topic:             str            = Field(min_length=1, max_length=2000)
    minutes:           float          = Field(gt=0, le=30)
    tone:              str
    language:          str
    story_structure:   str
    model_name:        str
    use_color_image:   bool
    max_output_tokens: int            = Field(gt=0, le=128_000)
    scene_params:      SceneParams
    pace_profile:      PaceProfile
    main_character:    str            = Field(min_length=1, max_length=500)
    target_platform:   TargetPlatform = TargetPlatform.TIKTOK 