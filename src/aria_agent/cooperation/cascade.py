"""Cascade / Escalation pattern.

Strategy:
1. Classify the task.
2. Try the cheap workhorse first.
3. Assess quality of the output (length + refusal detection).
4. If acceptable → return it. Done.
5. If not → escalate to the best-fit model for the task, retry.
6. If even the escalation fails → return the best output we got (with a warning).

Why this is useful: routine tasks (cron, bulk, simple Q&A) get answered by
the 99%-off model. Only the tasks that need real quality burn the credits
on a frontier model.

Cost-shape:
- Best case: cheap-only run, ~$0.06/attempt
- Worst case: cheap + best-fit, ~$0.06 + ~$25 = $25/attempt
- Average: usually cheap-only, occasional escalation
"""
import asyncio
from typing import Optional

try:
    from loguru import logger
except ImportError:  # pragma: no cover
    # No-op logger when loguru is not installed
    class _NoopLogger:
        def warning(self, *args, **kwargs): pass
        def info(self, *args, **kwargs): pass
        def exception(self, *args, **kwargs): pass
        def error(self, *args, **kwargs): pass
    logger = _NoopLogger()  # type: ignore

from shared_core.llm import LLMResponse

from ..providers.base import ProviderError
from ..providers.registry import ProviderRegistry
from ..router.selector import ModelSelector
from .base import (
    CooperationPattern,
    CooperationResult,
    StepResult,
    assess_quality,
)


class CascadePattern(CooperationPattern):
    """Try cheap → escalate if needed.

    The cheap workhorse is the default primary for the task type. The
    escalation target is the RoutingDecision's `escalation` field (Pro+ if
    available, else the best active specialist).
    """

    name: str = "cascade"

    async def execute(
        self,
        task: str,
        router: ModelSelector,
        registry: ProviderRegistry,
        *,
        budget: Optional[str] = None,
    ) -> CooperationResult:
        decision = router.select_for_task_description(task)
        primary = decision.primary

        # Cascade ALWAYS tries the cheap workhorse first, then escalates to the
        # task's primary model if quality is low. This is the whole point —
        # the cheap workhorse isn't typically the routing decision's primary.
        cheap_pool = router._table.cheap_pool()
        cheap = cheap_pool[0] if cheap_pool else primary
        # Best = the routing decision's primary; if no escalation target,
        # primary itself is both the routing choice and the escalation target.
        best = decision.escalation or decision.primary

        # If user forced "quality" budget, skip the cascade
        force_best = budget == "quality"

        # Step 1: cheap attempt
        if not force_best and cheap.model_id != best.model_id:
            cheap_step = await self._call_model(
                task=task,
                provider_name=cheap.provider_name,
                model_id=cheap.model_id,
                registry=registry,
                step_name="cheap_attempt",
            )
            quality = assess_quality(cheap_step.output_text)
            if quality.is_acceptable:
                return CooperationResult(
                    final_output=cheap_step.output_text,
                    pattern=self.name,
                    steps=[cheap_step],
                    total_cost_usd=cheap_step.cost_usd,
                    total_latency_ms=cheap_step.latency_ms,
                    metadata={
                        "cascade_outcome": "cheap_succeeded",
                        "quality_score": quality.score,
                        "primary_model": f"{cheap.provider_name}/{cheap.model_id}",
                    },
                )

            # Cheap didn't work — escalate. If the escalation target's
            # provider isn't registered, fall back gracefully.
            try:
                best_step = await self._call_model(
                    task=task,
                    provider_name=best.provider_name,
                    model_id=best.model_id,
                    registry=registry,
                    step_name="escalation",
                )
            except (KeyError, ProviderError) as e:
                # Escalation target unavailable. Return the cheap output with
                # a warning rather than crashing. The user got *something*,
                # even if not the best possible.
                logger.warning(
                    f"Cascade escalation to {best.provider_name}/{best.model_id} "
                    f"failed ({e}); returning cheap output with quality warning"
                )
                return CooperationResult(
                    final_output=cheap_step.output_text or "(no output produced)",
                    pattern=self.name,
                    steps=[cheap_step],
                    total_cost_usd=cheap_step.cost_usd,
                    total_latency_ms=cheap_step.latency_ms,
                    metadata={
                        "cascade_outcome": "escalation_failed_returned_cheap",
                        "cheap_quality_reason": quality.reason,
                        "escalation_error": str(e),
                        "cheap_model": f"{cheap.provider_name}/{cheap.model_id}",
                        "intended_escalation": f"{best.provider_name}/{best.model_id}",
                    },
                )
            return CooperationResult(
                final_output=best_step.output_text,
                pattern=self.name,
                steps=[cheap_step, best_step],
                total_cost_usd=cheap_step.cost_usd + best_step.cost_usd,
                total_latency_ms=cheap_step.latency_ms + best_step.latency_ms,
                metadata={
                    "cascade_outcome": "escalated",
                    "cheap_quality_reason": quality.reason,
                    "cheap_model": f"{cheap.provider_name}/{cheap.model_id}",
                    "escalation_model": f"{best.provider_name}/{best.model_id}",
                },
            )

        # Budget says "quality" or no cheap option — go straight to best
        best_step = await self._call_model(
            task=task,
            provider_name=best.provider_name,
            model_id=best.model_id,
            registry=registry,
            step_name="best_attempt",
        )
        return CooperationResult(
            final_output=best_step.output_text,
            pattern=self.name,
            steps=[best_step],
            total_cost_usd=best_step.cost_usd,
            total_latency_ms=best_step.latency_ms,
            metadata={
                "cascade_outcome": "best_only",
                "primary_model": f"{best.provider_name}/{best.model_id}",
            },
        )

    async def _call_model(
        self,
        task: str,
        provider_name: str,
        model_id: str,
        registry: ProviderRegistry,
        step_name: str,
    ) -> StepResult:
        """One model call. Wraps the registry + provider call in a StepResult."""
        try:
            provider = registry.get(provider_name)
            response: LLMResponse = await provider.chat(
                model=model_id,
                messages=[{"role": "user", "content": task}],
            )
            return StepResult(
                step_name=step_name,
                provider_name=provider_name,
                model_id=model_id,
                input_messages=[{"role": "user", "content": task}],
                output_text=response.text,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                latency_ms=response.latency_ms,
                cost_usd=response.estimated_cost,
                success=True,
            )
        except ProviderError as e:
            return StepResult(
                step_name=step_name,
                provider_name=provider_name,
                model_id=model_id,
                input_messages=[{"role": "user", "content": task}],
                output_text="",
                success=False,
                error=str(e),
            )
