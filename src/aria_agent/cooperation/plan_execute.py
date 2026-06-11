"""Plan-Execute-Validate pattern.

Three roles, three models, one task:

1. **Planner** (cheap workhorse): analyzes the task and produces a brief plan.
   The plan is "here's how I'd approach this" — not the final answer.

2. **Executor** (best-fit model for the task): takes the plan, does the work,
   produces the final answer. This is the model whose output the user sees.

3. **Validator** (a DIFFERENT model from both): reviews the executor's output,
   flags problems, and either approves or returns feedback for a retry.

If the validator approves, the executor's output is returned.
If the validator rejects, the executor retries with the feedback (up to N
retries). After max retries, the best output (by some metric, e.g. length)
is returned with a warning.

Why three models? The plan and the validation are independent judgments
about quality. Using the same model for both would be circular — the model
can't reliably catch its own mistakes. Using a different model for
validation (especially one with a different "perspective" — e.g. reasoning-
focused for code work) is a known pattern in production LLM systems.
"""
from typing import Optional

from shared_core.llm import LLMResponse

from ..providers.base import ProviderError
from ..providers.registry import ProviderRegistry
from ..router.selector import ModelSelector
from ..router.routing_table import ModelInfo
from .base import (
    CooperationPattern,
    CooperationResult,
    StepResult,
    assess_quality,
)


_PLANNER_PROMPT = """You are a planning assistant. Analyze the user's task and produce a short plan (3-5 numbered steps) describing how to approach it. Be specific and actionable. Output ONLY the numbered plan, no preamble or explanation.

Task: {task}

Plan:"""

_EXECUTOR_PROMPT = """You are the executor. Follow the plan below to complete the user's task. Produce the final answer.

Plan:
{plan}

Task: {task}

Answer:"""

_VALIDATOR_PROMPT = """You are a quality reviewer. Review the proposed answer below and check whether it actually and correctly addresses the task. Be specific about any issues.

Output format:
- VERDICT: APPROVE or REJECT
- REASON: <one sentence>
- FEEDBACK: <if REJECT, specific guidance for improvement; if APPROVE, write "none">

Task: {task}

Proposed answer:
{answer}

VERDICT:"""


class PlanExecuteValidatePattern(CooperationPattern):
    """Three-model pipeline: plan → execute → validate (with optional retry)."""

    name: str = "plan_execute_validate"

    def __init__(self, *, max_retries: int = 1, min_output_length: int = 50):
        self.max_retries = max_retries
        self.min_output_length = min_output_length

    async def execute(
        self,
        task: str,
        router: ModelSelector,
        registry: ProviderRegistry,
        *,
        budget: Optional[str] = None,
    ) -> CooperationResult:
        decision = router.select_for_task_description(task)
        executor_info = decision.primary
        # For planner/validator we want different models than the executor.
        # Planner: cheap workhorse (always)
        cheap_pool = router._table.cheap_pool()
        planner_info = cheap_pool[0] if cheap_pool else executor_info
        # Validator: prefer a reasoning-focused model, fall back to a
        # different model from the executor.
        validator_info = self._pick_validator(router, executor_info, planner_info)

        steps: list[StepResult] = []
        best_step: Optional[StepResult] = None
        best_score = -1.0
        feedback: Optional[str] = None

        for attempt in range(self.max_retries + 1):
            attempt_label = f"attempt_{attempt + 1}"

            # Step 1: plan (only on first attempt; reuse plan on retries)
            if attempt == 0:
                plan_step = await self._call_model(
                    task=_PLANNER_PROMPT.format(task=task),
                    provider_name=planner_info.provider_name,
                    model_id=planner_info.model_id,
                    registry=registry,
                    step_name=f"plan_{attempt_label}",
                )
                steps.append(plan_step)
                plan_text = plan_step.output_text or "(no plan produced)"
            else:
                plan_text = "(reusing plan from attempt 1)"

            # Step 2: execute
            executor_prompt = _EXECUTOR_PROMPT.format(plan=plan_text, task=task)
            if feedback:
                executor_prompt += f"\n\nReviewer feedback from previous attempt: {feedback}"

            execute_step = await self._call_model(
                task=executor_prompt,
                provider_name=executor_info.provider_name,
                model_id=executor_info.model_id,
                registry=registry,
                step_name=f"execute_{attempt_label}",
            )
            steps.append(execute_step)

            # Step 3: validate
            validator_prompt = _VALIDATOR_PROMPT.format(task=task, answer=execute_step.output_text)
            validate_step = await self._call_model(
                task=validator_prompt,
                provider_name=validator_info.provider_name,
                model_id=validator_info.model_id,
                registry=registry,
                step_name=f"validate_{attempt_label}",
            )
            steps.append(validate_step)

            # Track best step
            score = assess_quality(execute_step.output_text).score
            if score > best_score:
                best_score = score
                best_step = execute_step

            # Parse verdict
            verdict_text = validate_step.output_text.upper()
            if "APPROVE" in verdict_text and "REJECT" not in verdict_text:
                # Approved — return the executor's output
                return CooperationResult(
                    final_output=execute_step.output_text,
                    pattern=self.name,
                    steps=steps,
                    total_cost_usd=sum(s.cost_usd for s in steps),
                    total_latency_ms=sum(s.latency_ms for s in steps),
                    metadata={
                        "outcome": "approved",
                        "attempts": attempt + 1,
                        "planner": f"{planner_info.provider_name}/{planner_info.model_id}",
                        "executor": f"{executor_info.provider_name}/{executor_info.model_id}",
                        "validator": f"{validator_info.provider_name}/{validator_info.model_id}",
                    },
                )

            # Rejected — extract feedback and try again
            feedback = self._extract_feedback(validate_step.output_text)
            if attempt >= self.max_retries:
                break

        # Exhausted retries — return the best step we have
        return CooperationResult(
            final_output=best_step.output_text if best_step else "(no output produced)",
            pattern=self.name,
            steps=steps,
            total_cost_usd=sum(s.cost_usd for s in steps),
            total_latency_ms=sum(s.latency_ms for s in steps),
            metadata={
                "outcome": "max_retries_exceeded",
                "attempts": len(steps) // 3,
                "planner": f"{planner_info.provider_name}/{planner_info.model_id}",
                "executor": f"{executor_info.provider_name}/{executor_info.model_id}",
                "validator": f"{validator_info.provider_name}/{validator_info.model_id}",
            },
        )

    def _pick_validator(
        self, router: ModelSelector, executor: ModelInfo, planner: ModelInfo
    ) -> ModelInfo:
        """Pick a model for the validator role.

        Preference order:
        1. A reasoning-focused model that isn't the executor or planner
        2. Any other model that isn't the executor
        3. The default model (last resort)
        """
        all_models = router._table.all()
        # Try to find a reasoning specialist that isn't already in use
        reasoning_models = [
            m for m in all_models
            if "reasoning" in m.task_types
            and m.model_id != executor.model_id
            and m.model_id != planner.model_id
        ]
        if reasoning_models:
            return reasoning_models[0]
        # Fall back to any other model
        other = [
            m for m in all_models
            if m.model_id != executor.model_id
            and m.model_id != planner.model_id
        ]
        if other:
            return other[0]
        # Last resort: use the executor (better than nothing)
        return executor

    def _extract_feedback(self, validator_output: str) -> Optional[str]:
        """Pull the FEEDBACK line out of the validator's response."""
        for line in validator_output.splitlines():
            if line.strip().upper().startswith("FEEDBACK:"):
                return line.split(":", 1)[1].strip()
        # Fall back to the whole output if structured parsing failed
        return validator_output.strip() or None

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
