"""Specialized ensemble pattern.

Strategy:
1. Classify the task.
2. Pick the top N models for this task (N defaults to 2 — the primary + 1 specialist).
3. Call them in parallel with the same prompt.
4. Pick the best output using a simple metric (longest non-refusal response).

Why parallel? Independent calls give independent perspectives. The user gets
to see the diversity in the trace. The combiner picks the best.

This is the simplest cooperation pattern. For more sophisticated ensembling
(self-consistency, voting, debate), the pattern would need a much more
involved combiner. v1 keeps it pragmatic.
"""
import asyncio
from typing import Optional

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


class EnsemblePattern(CooperationPattern):
    """Parallel calls + simple pick-best combiner.

    v1 picks the longest non-refusal output. v2 can use a model-as-judge
    combiner (which is just a nested cooperation pattern — PlanExecuteValidate
    with the ensemble output as the "executor" step).
    """

    name: str = "ensemble"

    def __init__(self, *, num_models: int = 2):
        if num_models < 1:
            raise ValueError("num_models must be >= 1")
        self.num_models = num_models

    async def execute(
        self,
        task: str,
        router: ModelSelector,
        registry: ProviderRegistry,
        *,
        budget: Optional[str] = None,
    ) -> CooperationResult:
        decision = router.select_for_task_description(task)
        # Pick num_models: primary + next best specialist (different from primary)
        candidates: list[tuple[str, str]] = [
            (decision.primary.provider_name, decision.primary.model_id)
        ]
        for m in decision.fallback, decision.escalation:
            if m is None:
                continue
            if len(candidates) >= self.num_models:
                break
            mid = (m.provider_name, m.model_id)
            if mid not in candidates:
                candidates.append(mid)
        # If we still have only 1, add the cheap workhorse as a diversity pick
        if len(candidates) < self.num_models:
            for m in router._table.cheap_pool():
                mid = (m.provider_name, m.model_id)
                if mid not in candidates:
                    candidates.append(mid)
                if len(candidates) >= self.num_models:
                    break

        # Call all models in parallel
        steps = await asyncio.gather(*[
            self._call_model(
                task=task,
                provider_name=pn,
                model_id=mid,
                registry=registry,
                step_name=f"ensemble_{i + 1}",
            )
            for i, (pn, mid) in enumerate(candidates)
        ])

        # Pick the best: longest non-refusal output
        best_step = max(
            steps,
            key=lambda s: (
                assess_quality(s.output_text).score,
                len(s.output_text or ""),
            ),
        )

        return CooperationResult(
            final_output=best_step.output_text or "(no output produced)",
            pattern=self.name,
            steps=list(steps),
            total_cost_usd=sum(s.cost_usd for s in steps),
            total_latency_ms=sum(s.latency_ms for s in steps),
            metadata={
                "outcome": "ensemble",
                "models_called": [f"{pn}/{mid}" for pn, mid in candidates],
                "winner": f"{best_step.provider_name}/{best_step.model_id}",
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
