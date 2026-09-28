# src/core/scripts/base_text_engine.py
# ──────────────────────────────────────────────────────────────────────────────
# TẦNG 2A — BaseTextEngine (cho Claude, Gemini text)
# ──────────────────────────────────────────────────────────────────────────────

from abc import abstractmethod
from typing import Any, List, Optional

from ...utils.logger import get_logger

from ..base_ai_engine import BaseEngine, ContentFilter, GenerationResult, ModerationAction, ModerationResult

logger = get_logger(__name__)

class BaseTextEngine(BaseEngine):
    """
    Mở rộng BaseEngine cho text generation.
    Thêm: token limit, content filter, budget cap, cost tracking.

    Kế thừa: ClaudeEngine, GeminiEngine (text mode).
    """

    def __init__(
        self,
        model_name:              str,
        env_var:                 str,
        max_output_tokens:       int   = 4000,
        max_input_tokens_limit:  int   = 2500,
        temperature:             float = 1.0,
        input_cost_per_1k:       float = 0.0,
        output_cost_per_1k:      float = 0.0,
        session_budget_usd:      Optional[float] = None,
        content_filter:          Optional[ContentFilter] = None,
        auto_use_cleaned_prompt: bool = True,
        **kwargs,  
    ) -> None:
        super().__init__(model_name=model_name, env_var=env_var, **kwargs)

        if not (0.0 <= temperature <= 2.0):
            raise ValueError("temperature phải trong khoảng [0.0, 2.0].")

        self.max_output_tokens       = max_output_tokens
        self.max_input_tokens_limit  = max_input_tokens_limit
        self.temperature             = temperature
        self.input_cost_per_1k       = input_cost_per_1k
        self.output_cost_per_1k      = output_cost_per_1k
        self.session_budget_usd      = session_budget_usd
        self.auto_use_cleaned_prompt = auto_use_cleaned_prompt
        self._filter                 = content_filter or ContentFilter()

    # ── Public API ───────────────────────────────────────────

    async def generate(
        self,
        prompt:             str,
        system_instruction: Optional[str] = None,
        stop_sequences:     Optional[List[str]] = None,
    ) -> GenerationResult:
        """validate → moderate → budget → retry → log."""
        self._validate_length(prompt)

        mod_result = self._filter.check(prompt)
        self._log_moderation(mod_result)

        if not mod_result.is_allowed:
            self._stats.record_moderated()
            raise ValueError(
                "Prompt bị từ chối: " + "; ".join(v.detail for v in mod_result.violations)
            )

        effective_prompt = (
            mod_result.cleaned_prompt
            if self.auto_use_cleaned_prompt and mod_result.cleaned_prompt
            else prompt
        )
        self._check_budget()

        async def call():
            return await self._call_api(effective_prompt, system_instruction, stop_sequences)

        result, latency = await self._run_with_retry(call)
        result.latency_ms = latency
        result.moderation = mod_result
        self._stats.record_success(
            latency_ms    = latency,
            cost          = result.cost,
            input_tokens  = result.input_tokens,
            output_tokens = result.output_tokens,
        )
        logger.info(
            "[%s] OK | tokens=%d+%d | cost=$%.6f | %.0fms",
            self.model_name, result.input_tokens, result.output_tokens,
            result.cost, latency,
        )
        return result

    # ── Abstract ─────────────────────────────────────────────

    @abstractmethod
    async def _call_api(
        self,
        prompt:             str,
        system_instruction: Optional[str],
        stop_sequences:     Optional[List[str]],
        **kwargs: Any,  
    ) -> GenerationResult:
        pass

    # ── Guards ───────────────────────────────────────────────

    def _validate_length(self, prompt: str) -> None:
        if not prompt or not prompt.strip():
            raise ValueError("Prompt không được rỗng.")
        estimated = self.estimate_token_count(prompt)
        if estimated > self.max_input_tokens_limit:
            raise ValueError(
                f"Prompt ước tính {estimated} tokens, vượt giới hạn {self.max_input_tokens_limit}."
            )

    def _check_budget(self) -> None:
        if (
            self.session_budget_usd is not None
            and self._stats.total_cost >= self.session_budget_usd
        ):
            raise RuntimeError(
                f"Đã đạt ngưỡng chi phí: "
                f"${self._stats.total_cost:.4f} / ${self.session_budget_usd:.4f}"
            )

    def _log_moderation(self, result: ModerationResult) -> None:
        for v in result.violations:
            fn = logger.warning if v.action == ModerationAction.BLOCK else logger.info
            fn("[Moderation] %s | %s | %s", v.violation_type.value, v.action.value, v.detail)

    # ── Utilities ────────────────────────────────────────────

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        return round(
            (input_tokens  / 1_000_000) * self.input_cost_per_1k
            + (output_tokens / 1_000_000) * self.output_cost_per_1k,
            6,
        )

    def estimate_token_count(self, text: str) -> int:
        """Override ở lớp con bằng tokenizer thực của provider."""
        return max(1, len(text) // 4)

    def remaining_budget(self) -> Optional[float]:
        if self.session_budget_usd is None:
            return None
        return max(0.0, self.session_budget_usd - self._stats.total_cost)

    @property
    def filter(self) -> ContentFilter:
        return self._filter

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"model={self.model_name!r}, "
            f"budget=${self.session_budget_usd})"
        )

