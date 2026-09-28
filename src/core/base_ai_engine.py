# src/core/base_ai_engine.py

from abc import ABC, abstractmethod
from src.config import settings
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from ..utils.logger import get_logger
import asyncio
import re
import time

logger = get_logger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# TẦNG 0 — SHARED TYPES (dùng chung cho mọi engine)
# ──────────────────────────────────────────────────────────────────────────────

class ViolationType(str, Enum):
    BLOCKED_WORD     = "blocked_word"
    TOXIC_CONTENT    = "toxic_content"
    PII_DETECTED     = "pii_detected"
    INPUT_TOO_LONG   = "input_too_long"
    PROMPT_INJECTION = "prompt_injection"


class ModerationAction(str, Enum):
    BLOCK  = "block"
    REDACT = "redact"
    WARN   = "warn"


class FinishReason(str, Enum):
    STOP      = "stop"
    MAX_TOKENS= "max_tokens"
    ERROR     = "error"
    TIMEOUT   = "timeout"
    MODERATED = "moderated"


@dataclass
class ModerationViolation:
    violation_type: ViolationType
    action:         ModerationAction
    detail:         str
    matched_value:  Optional[str] = None


@dataclass
class ModerationResult:
    is_allowed:     bool
    violations:     List[ModerationViolation] = field(default_factory=list)
    cleaned_prompt: Optional[str] = None


@dataclass
class GenerationResult:
    """Kết quả text generation — dùng cho ClaudeEngine, GeminiEngine text."""
    content:       str
    input_tokens:  int
    output_tokens: int
    cost:          float
    finish_reason: FinishReason
    latency_ms:    float
    model_name:    str
    moderation:    Optional[ModerationResult] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content":       self.content,
            "input_tokens":  self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens":  self.total_tokens,
            "cost":          self.cost,
            "finish_reason": self.finish_reason.value,
            "latency_ms":    self.latency_ms,
            "model_name":    self.model_name,
            "timestamp":     self.timestamp.isoformat(),
            "violations": [
                {"type": v.violation_type.value, "action": v.action.value, "detail": v.detail}
                for v in (self.moderation.violations if self.moderation else [])
            ],
        }


@dataclass
class ImageResult:
    """Kết quả image generation — dùng cho NanaBananaEngine."""
    saved_path:   Optional[str]   # None nếu model không trả về ảnh
    model_name:   str
    prompt:       str
    latency_ms:   float
    success:      bool
    error:        Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "saved_path": self.saved_path,
            "model_name": self.model_name,
            "prompt":     self.prompt[:100],
            "latency_ms": self.latency_ms,
            "success":    self.success,
            "error":      self.error,
            "timestamp":  self.timestamp.isoformat(),
        }

@dataclass
class VoiceResult:
    """Kết quả voice generation — dùng cho VoiceEngine."""
    saved_path:   Optional[str]   # None nếu model không trả về audio
    model_name:   str
    text:         str
    latency_ms:   float
    success:      bool
    error:        Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "saved_path": self.saved_path,
            "model_name": self.model_name,
            "text":       self.text[:100],
            "latency_ms": self.latency_ms,
            "success":    self.success,
            "error":      self.error,
            "timestamp":  self.timestamp.isoformat(),
        }

@dataclass
class UsageStats:
    total_requests:      int   = 0
    successful_requests: int   = 0
    failed_requests:     int   = 0
    moderated_requests:  int   = 0
    total_input_tokens:  int   = 0
    total_output_tokens: int   = 0
    total_cost:          float = 0.0
    total_latency_ms:    float = 0.0

    @property
    def average_latency_ms(self) -> float:
        return self.total_latency_ms / self.successful_requests if self.successful_requests else 0.0

    @property
    def success_rate(self) -> float:
        return self.successful_requests / self.total_requests if self.total_requests else 0.0

    def record_success(self, latency_ms: float, cost: float = 0.0,
                       input_tokens: int = 0, output_tokens: int = 0) -> None:
        self.total_requests      += 1
        self.successful_requests += 1
        self.total_input_tokens  += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost          += cost
        self.total_latency_ms    += latency_ms

    def record_failure(self) -> None:
        self.total_requests  += 1
        self.failed_requests += 1

    def record_moderated(self) -> None:
        self.total_requests     += 1
        self.moderated_requests += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_requests":      self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests":     self.failed_requests,
            "moderated_requests":  self.moderated_requests,
            "success_rate":        round(self.success_rate, 4),
            "total_input_tokens":  self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cost_usd":      round(self.total_cost, 6),
            "avg_latency_ms":      round(self.average_latency_ms, 2),
        }


# ──────────────────────────────────────────────────────────────────────────────
# TẦNG 1A — ContentFilter (dùng chung cho text engine)
# ──────────────────────────────────────────────────────────────────────────────

class ContentFilter:
    _DEFAULT_BLOCKED_WORDS: Set[str] = {
        "chết mẹ", "địt", "đụ", "cặc", "lồn", "con đĩ", "chịch",
        "thằng chó", "mẹ mày", "đồ ngu", "đồ chó",
        "fuck", "shit", "bitch", "asshole", "nigger",
        "kill yourself", "go die",
    }
    _DANGEROUS_PATTERNS: List[re.Pattern] = [
        re.compile(r"\b(cách\s+(làm|chế tạo|tổng hợp)\s+(bom|chất nổ|ma túy|vũ khí))\b", re.I),
        re.compile(r"\b(how\s+to\s+(make|build|synthesize)\s+(bomb|explosive|drug|weapon))\b", re.I),
        re.compile(r"\b(tự\s*tử|suicide\s*method)\b", re.I),
    ]
    _PII_PATTERNS: List[tuple[str, re.Pattern, str]] = [
        ("email",    re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"), "[EMAIL]"),
        ("phone",    re.compile(r"(\+84|0)[3-9]\d{8}"),                              "[SDT]"),
        ("cccd",     re.compile(r"\b\d{9}(\d{3})?\b"),                               "[CCCD]"),
        ("credit",   re.compile(r"\b(?:\d[ -]?){15,16}\b"),                          "[CARD]"),
        ("password", re.compile(r"(password|mật\s*khẩu)\s*[=:]\s*\S+", re.I),      "[PASSWORD]"),
    ]
    _INJECTION_PATTERNS: List[re.Pattern] = [
        re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?", re.I),
        re.compile(r"bỏ\s*qua\s*(tất\s*cả\s*)?(hướng\s*dẫn|lệnh)\s*(trước|trên)", re.I),
        re.compile(r"(you\s+are\s+now|từ\s+bây\s+giờ\s+bạn\s+là)\s+.{0,60}", re.I),
        re.compile(r"system\s*prompt\s*[:=]", re.I),
        re.compile(r"<\s*(system|instruction|prompt)\s*>", re.I),
    ]

    def __init__(
        self,
        extra_blocked_words:    Optional[Set[str]] = None,
        toxicity_threshold:     float = 0.75,
        pii_action:             ModerationAction = ModerationAction.REDACT,
        enable_injection_check: bool = True,
    ):
        self.blocked_words      = self._DEFAULT_BLOCKED_WORDS | (extra_blocked_words or set())
        self.toxicity_threshold = toxicity_threshold
        self.pii_action         = pii_action
        self.enable_injection   = enable_injection_check

    def check(self, prompt: str) -> ModerationResult:
        violations: List[ModerationViolation] = []
        working = prompt

        if self.enable_injection:
            inj = self._check_injection(working)
            if inj:
                violations.append(inj)

        violations.extend(self._check_blocked_words(working))

        tox = self._check_toxicity(working)
        if tox:
            violations.append(tox)

        working, pii_viols = self._check_pii(working)
        violations.extend(pii_viols)

        is_blocked = any(v.action == ModerationAction.BLOCK for v in violations)
        return ModerationResult(
            is_allowed    = not is_blocked,
            violations    = violations,
            cleaned_prompt= working if working != prompt else None,
        )

    def _check_injection(self, text: str) -> Optional[ModerationViolation]:
        for p in self._INJECTION_PATTERNS:
            m = p.search(text)
            if m:
                return ModerationViolation(ViolationType.PROMPT_INJECTION,
                                           ModerationAction.BLOCK,
                                           "Phát hiện dấu hiệu prompt injection.",
                                           m.group(0))
        return None

    def _check_blocked_words(self, text: str) -> List[ModerationViolation]:
        violations, lower = [], text.lower()
        for word in self.blocked_words:
            if word.lower() in lower:
                violations.append(ModerationViolation(
                    ViolationType.BLOCKED_WORD, ModerationAction.BLOCK,
                    f"Từ/cụm từ bị cấm: '{word}'.", word))
        for p in self._DANGEROUS_PATTERNS:
            m = p.search(text)
            if m:
                violations.append(ModerationViolation(
                    ViolationType.BLOCKED_WORD, ModerationAction.BLOCK,
                    "Nội dung nguy hiểm phát hiện qua pattern.", m.group(0)))
        return violations

    def _check_toxicity(self, text: str) -> Optional[ModerationViolation]:
        score = self._score_toxicity(text)
        if score >= self.toxicity_threshold:
            return ModerationViolation(ViolationType.TOXIC_CONTENT, ModerationAction.BLOCK,
                                       f"Điểm độc hại {score:.2f} vượt ngưỡng {self.toxicity_threshold:.2f}.",
                                       str(round(score, 4)))
        return None

    def _score_toxicity(self, text: str) -> float:
        if not text:
            return 0.0
        upper   = sum(1 for c in text if c.isupper()) / max(len(text), 1)
        exclaim = text.count("!") / max(len(text), 1)
        quest   = text.count("?") / max(len(text), 1)
        return min((upper * 0.5) + (exclaim * 30) + (quest * 10), 1.0)

    def _check_pii(self, text: str) -> tuple[str, List[ModerationViolation]]:
        violations = []
        for label, pattern, replacement in self._PII_PATTERNS:
            matches = pattern.findall(text)
            if matches:
                text = pattern.sub(replacement, text)
                violations.append(ModerationViolation(
                    ViolationType.PII_DETECTED, self.pii_action,
                    f"Phát hiện {label.upper()} — đã {'ẩn' if self.pii_action == ModerationAction.REDACT else 'chặn'}.",
                    str(matches[0])))
        return text, violations

    def add_blocked_words(self, words: Set[str]) -> None:
        self.blocked_words |= words

    def remove_blocked_words(self, words: Set[str]) -> None:
        self.blocked_words -= words

    def get_blocked_words(self) -> Set[str]:
        return frozenset(self.blocked_words)


# ──────────────────────────────────────────────────────────────────────────────
# TẦNG 1B — BaseEngine (hạ tầng chung nhất — mọi engine đều kế thừa)
# ──────────────────────────────────────────────────────────────────────────────

class BaseEngine(ABC):
    """
    Hạ tầng tối thiểu cho MỌI engine (text + image + audio...).

    Cung cấp:
      - model_name, api_key
      - UsageStats
      - retry loop với exponential backoff
      - context manager async
      - _is_retryable() abstract

    KHÔNG có: token limit, content filter, budget — những thứ đó
    chỉ phù hợp với text generation.
    """

    def __init__(
        self,
        model_name:       str,
        env_var:          str           = "",
        max_retries:      int           = 3,
        retry_base_delay: float         = 1.0,
        retry_max_delay:  float         = 30.0,
        timeout:          int           = 60,
    ) -> None:
        if not model_name:
            raise ValueError("model_name không được để trống.")
        
        self.model_name       = model_name
        self.api_key          = self._load_api_key(env_var)
        self.max_retries      = max_retries
        self.retry_base_delay = retry_base_delay
        self.retry_max_delay  = retry_max_delay
        self.timeout          = timeout
        self._stats           = UsageStats()

    # ── Context manager ──────────────────────────────────────

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self._close()

    async def _close(self) -> None:
        """Override ở lớp con nếu cần cleanup (đóng HTTP client...)."""
        pass

    # ── Retry loop dùng chung ────────────────────────────────

    async def _run_with_retry(self, coro_fn) -> Any:
        """
        Chạy coro_fn() với retry + exponential backoff.
        coro_fn là một callable trả về coroutine (lambda async).

        Raises RuntimeError nếu hết số lần thử.
        """
        last_error: Optional[Exception] = None
        start_time = time.monotonic()

        for attempt in range(1, self.max_retries + 1):
            try:
                result = await coro_fn()
                latency = (time.monotonic() - start_time) * 1000
                return result, latency
            except Exception as exc:
                last_error = exc
                if not self._is_retryable(exc) or attempt == self.max_retries:
                    break
                delay = min(self.retry_base_delay * (2 ** (attempt - 1)), self.retry_max_delay)
                logger.warning(
                    "[%s] Lỗi lần %d/%d: %s — thử lại sau %.1fs",
                    self.model_name, attempt, self.max_retries, exc, delay,
                )
                await asyncio.sleep(delay)

        self._stats.record_failure()
        raise RuntimeError(f"[{self.model_name}] Thất bại sau {self.max_retries} lần thử.") from last_error

    # ── Abstract ─────────────────────────────────────────────


    @abstractmethod
    def _is_retryable(self, error: Exception) -> bool:
        pass

    # ── Stats ────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        return self._stats.to_dict()

    def reset_stats(self) -> None:
        self._stats = UsageStats()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model={self.model_name!r})"

    @staticmethod
    def _load_api_key(env_var: str) -> str:
        """Logic ưu tiên API Key truyền vào -> Biến môi trường"""
        key = getattr(settings, env_var, None)
        
        if key:
            return key
            
        raise ValueError(f"Thiếu API key. Set biến môi trường {env_var}.")