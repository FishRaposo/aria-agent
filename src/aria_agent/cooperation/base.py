"""Base abstractions for cooperation patterns.

A `CooperationPattern` orchestrates multiple model calls to complete one task.
The contract is:

- `execute(task: str, router, registry) -> CooperationResult`
- Async, returns a structured result with all steps
- Failures in one step may be retried, escalated, or surfaced depending on the pattern

`CooperationResult` and `StepResult` are the structured outputs the agent
layer surfaces to the API gateway.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..providers.registry import ProviderRegistry
    from ..router.selector import ModelSelector


@dataclass
class StepResult:
    """One model's contribution to a cooperation run.

    Records which model was used, what was sent, what came back, and how it
    performed. Used by the trace layer to show the user what happened.
    """

    step_name: str                          # e.g. "primary_attempt", "escalation", "validate"
    provider_name: str
    model_id: str
    input_messages: list[dict]
    output_text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    success: bool = True
    error: Optional[str] = None

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class CooperationResult:
    """The final result of a cooperation run.

    `final_output` is what the agent returns. `steps` is the full transcript
    (every model call, including failed/retried ones).
    """

    final_output: str
    pattern: str                            # "cascade" | "plan_execute_validate" | "ensemble"
    steps: list[StepResult] = field(default_factory=list)
    total_cost_usd: float = 0.0
    total_latency_ms: float = 0.0
    metadata: dict = field(default_factory=dict)

    @property
    def num_steps(self) -> int:
        return len(self.steps)

    @property
    def num_models_used(self) -> int:
        return len(set(f"{s.provider_name}/{s.model_id}" for s in self.steps))


@dataclass
class QualityAssessment:
    """Result of the cheap-model-output quality check (used by cascade).

    `is_acceptable` is the verdict. `reason` explains why (for the trace).
    """

    is_acceptable: bool
    score: float                            # 0.0-1.0; higher = better
    reason: str = ""
    metrics: dict = field(default_factory=dict)


# Quality thresholds (tunable). Used by assess_quality below.
_MIN_OUTPUT_LENGTH = 20                    # shorter than this → likely error
_REFUSAL_MARKERS = (
    "i can't help with that",
    "i cannot help with that",
    "i'm not able to",
    "i am not able to",
    "as an ai",
    "i apologize, but",
    "i'm sorry, but",
)


def assess_quality(output: str, *, min_length: int = _MIN_OUTPUT_LENGTH) -> QualityAssessment:
    """Heuristic quality check on a model's output.

    Returns a verdict + a score. Used by the cascade pattern to decide whether
    to escalate. v1 is rule-based (length + refusal detection); v2 can add
    LLM-as-judge for higher fidelity.
    """
    if not output:
        return QualityAssessment(
            is_acceptable=False, score=0.0,
            reason="Empty output",
            metrics={"length": 0},
        )

    stripped = output.strip()
    length = len(stripped)

    # Refusal detection
    lowered = stripped.lower()
    refusal = any(marker in lowered for marker in _REFUSAL_MARKERS)

    # Length score (sigmoid-ish: 0 at min_length, 1 at 2x min_length)
    if length < min_length:
        length_score = 0.0
    else:
        length_score = min(1.0, (length - min_length) / min_length)

    if refusal:
        score = 0.0
        reason = f"Refusal marker detected (length {length})"
    elif length < min_length:
        score = 0.1
        reason = f"Output too short ({length} chars, want >= {min_length})"
    else:
        score = length_score
        reason = f"OK (length {length})"

    return QualityAssessment(
        is_acceptable=score >= 0.5 and not refusal,
        score=score,
        reason=reason,
        metrics={"length": length, "refusal": refusal, "length_score": length_score},
    )


class CooperationPattern(ABC):
    """Abstract base for cooperation patterns.

    Subclasses implement `execute` to orchestrate one or more model calls.
    The agent layer picks a pattern (or accepts a user-chosen one) and calls
    `execute` once per task.
    """

    name: str = "abstract"

    @abstractmethod
    async def execute(
        self,
        task: str,
        router: "ModelSelector",
        registry: "ProviderRegistry",
        *,
        budget: Optional[str] = None,
    ) -> CooperationResult:
        """Run the cooperation pattern on a task.

        Args:
            task: The user's request (free-form text)
            router: ModelSelector for picking the right model per step
            registry: ProviderRegistry for resolving (provider, model) to live clients
            budget: Optional override — "cheap" | "balanced" | "quality"

        Returns:
            CooperationResult with the final output and full step transcript.
        """
