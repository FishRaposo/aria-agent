"""Orchestrator — high-level task decomposition + sub-agent dispatch.

The Orchestrator takes a high-level task and dispatches it to multiple
sub-agents in two modes:

1. **Parallel** — fan out to N sub-agents simultaneously (asyncio.gather).
   Use when sub-agents are independent (planner + architect + researcher
   for the same task). Total latency = max(individual latencies), not
   sum.

2. **Sequential** — chain sub-agents, passing prior output as context.
   Use when sub-agents depend on each other (planner → implementer →
   validator). Total latency = sum(individual latencies), but each
   subsequent agent benefits from earlier agents' work.

**Why this matters:**

For a task like "design and implement a /health endpoint":
- Parallel: {planner, architect, researcher} → all 3 run at once, get
  independent perspectives, ~3s total instead of 9s.
- Sequential: planner → implementer → validator → implementer benefits
  from plan, validator catches issues, ~9s but higher quality.

The Orchestrator lets callers choose. It's also a building block for
more complex orchestration (e.g., 2-level: planner + (implementer ||
tester) → validator) — the user can compose these manually.

**Per-request state:** the Orchestrator is constructed once at app startup
and shared. Each `run_parallel` / `run_sequential` call is independent
(returns a fresh `OrchestrationResult` with no shared mutable state).
"""
import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional, Sequence

from ..router.routing_table import SubAgentRole
from .base import SubAgentResult
from .registry import SubAgentRegistry


@dataclass
class OrchestrationStep:
    """One sub-agent's contribution to an orchestration run.

    Wraps a SubAgentResult with the role name + timing info. Used by
    `OrchestrationResult` to show the user what each sub-agent did.
    """

    role: SubAgentRole
    result: SubAgentResult
    step_index: int                            # 0-based order
    wall_clock_ms: float = 0.0                 # total time including overhead


@dataclass
class OrchestrationResult:
    """The result of a parallel or sequential orchestration run.

    `final_output` is a synthesis of the per-step outputs:
    - Parallel mode: concatenates the per-step outputs (each on its own)
    - Sequential mode: returns the LAST sub-agent's output (each got
      prior context; the last one is the final answer)

    `steps` is the full per-step transcript for debugging.
    """

    final_output: str
    mode: str                                  # "parallel" | "sequential"
    steps: list[OrchestrationStep] = field(default_factory=list)
    total_cost_usd: float = 0.0
    total_latency_ms: float = 0.0
    metadata: dict = field(default_factory=dict)

    @property
    def num_steps(self) -> int:
        return len(self.steps)

    @property
    def num_models_used(self) -> int:
        return len(set(f"{s.result.provider_name}/{s.result.model_id}" for s in self.steps))

    @property
    def num_succeeded(self) -> int:
        return sum(1 for s in self.steps if s.result.success)

    @property
    def num_failed(self) -> int:
        return sum(1 for s in self.steps if not s.result.success)


class Orchestrator:
    """High-level orchestrator that fans out / chains sub-agents.

    The orchestrator is intentionally simple:
    - `run_parallel`: asyncio.gather over N sub-agents
    - `run_sequential`: for-loop, passing prior output as context

    More complex patterns (2-level orchestration, conditional branching,
    retry-on-failure) are built by composing these primitives.

    Args:
        sub_agent_registry: SubAgentRegistry that resolves role → SubAgent
    """

    def __init__(self, sub_agent_registry: SubAgentRegistry):
        self._registry = sub_agent_registry

    async def run_parallel(
        self,
        task: str,
        roles: Sequence[SubAgentRole],
        *,
        budget: Optional[str] = None,
    ) -> OrchestrationResult:
        """Run multiple sub-agents in parallel on the same task.

        Each sub-agent gets the full task. They don't see each other's
        outputs. Use this when the sub-agents provide independent
        perspectives (planner + architect + researcher for the same
        problem).

        Args:
            task: The shared task
            roles: List of sub-agent roles to run in parallel
            budget: Optional budget override ("cheap" | "balanced" | "quality")
                   Applied to ALL sub-agents in this run.

        Returns:
            OrchestrationResult with per-step transcript + synthesized output.
            final_output concatenates each sub-agent's output.
        """
        if not roles:
            raise ValueError("roles must be a non-empty sequence")

        start = time.time()

        # Build coroutines
        coros = []
        for role in roles:
            sub_agent = self._registry.get(role)
            coros.append(self._run_one(sub_agent, task, role, index=len(coros)))

        # Run in parallel
        raw_results = await asyncio.gather(*coros, return_exceptions=False)

        total_latency_ms = (time.time() - start) * 1000.0
        total_cost = sum(r.result.cost_usd for r in raw_results)

        # Synthesize the final output
        final_output = self._synthesize_parallel(raw_results, task)

        return OrchestrationResult(
            final_output=final_output,
            mode="parallel",
            steps=list(raw_results),
            total_cost_usd=total_cost,
            total_latency_ms=total_latency_ms,
            metadata={
                "mode": "parallel",
                "roles": [r.role.value for r in raw_results],
                "budget": budget,
                "task_preview": task[:100],
            },
        )

    async def run_sequential(
        self,
        task: str,
        roles: Sequence[SubAgentRole],
        *,
        budget: Optional[str] = None,
        pass_full_output: bool = True,
    ) -> OrchestrationResult:
        """Run sub-agents sequentially, passing prior output as context.

        Each subsequent sub-agent sees all prior outputs in its context.
        The final sub-agent's output is the OrchestrationResult's
        final_output.

        Args:
            task: The shared task
            roles: Ordered list of sub-agent roles (planner → implementer
                   → validator, etc.)
            budget: Optional budget override
            pass_full_output: If True, pass the full prior output to each
                   subsequent sub-agent. If False, only the last prior
                   output is passed. Pass False for long-context savings.

        Returns:
            OrchestrationResult with per-step transcript + the LAST
            sub-agent's output as final_output.
        """
        if not roles:
            raise ValueError("roles must be a non-empty sequence")

        start = time.time()
        steps: list[OrchestrationStep] = []
        context: Optional[str] = None
        last_result: Optional[SubAgentResult] = None

        for index, role in enumerate(roles):
            sub_agent = self._registry.get(role)
            step = await self._run_one(
                sub_agent, task, role, index=index, context=context,
            )
            steps.append(step)
            last_result = step.result

            # Build context for the next sub-agent
            if pass_full_output:
                # Concatenate all prior outputs
                prior_chunks = []
                for s in steps:
                    prior_chunks.append(
                        f"=== {s.role.value} ({s.result.model_id}) ===\n"
                        f"{s.result.output_text}"
                    )
                context = "\n\n".join(prior_chunks)
            else:
                # Just the last output
                context = step.result.output_text

        total_latency_ms = (time.time() - start) * 1000.0
        total_cost = sum(s.result.cost_usd for s in steps)

        return OrchestrationResult(
            final_output=last_result.output_text if last_result else "",
            mode="sequential",
            steps=steps,
            total_cost_usd=total_cost,
            total_latency_ms=total_latency_ms,
            metadata={
                "mode": "sequential",
                "roles": [s.role.value for s in steps],
                "budget": budget,
                "pass_full_output": pass_full_output,
                "task_preview": task[:100],
            },
        )

    async def _run_one(
        self,
        sub_agent,
        task: str,
        role: SubAgentRole,
        index: int,
        context: Optional[str] = None,
    ) -> OrchestrationStep:
        """Run a single sub-agent and wrap in an OrchestrationStep."""
        start = time.time()
        result: SubAgentResult = await sub_agent.run(task, context=context)
        wall_clock_ms = (time.time() - start) * 1000.0
        return OrchestrationStep(
            role=role,
            result=result,
            step_index=index,
            wall_clock_ms=wall_clock_ms,
        )

    def _synthesize_parallel(
        self, steps: list[OrchestrationStep], task: str,
    ) -> str:
        """Synthesize the final output for a parallel run.

        Concatenates each sub-agent's output with a clear separator.
        """
        chunks = []
        for s in steps:
            header = f"=== {s.role.value} (model: {s.result.model_id}) ==="
            if s.result.success:
                chunks.append(f"{header}\n{s.result.output_text}")
            else:
                chunks.append(f"{header}\n[ERROR: {s.result.error}]")
        return "\n\n".join(chunks)
