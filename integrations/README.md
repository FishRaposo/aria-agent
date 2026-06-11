# Command Code Integration

Aria Agent integrates with Command Code via the `aria-subagents` skill.
The skill is installed at `~/.hermes/skills/software-development/aria-subagents/SKILL.md`
and provides full documentation for invoking Aria sub-agents from CMD's
agent loop.

## Quick example (from CMD's --print mode)

```bash
# Start the Aria server (one-time setup, in a separate terminal)
cd ~/work/aria-agent && make serve

# Use CMD with a prompt that triggers the aria-subagents skill
cmd --print "Use the aria planner sub-agent to design a /health endpoint for a FastAPI app"
```

CMD will read the `aria-subagents` skill, then make a call like:

```python
import asyncio
from aria_agent.subagents import get_default_sub_agent_registry
from aria_agent.router import ModelSelector, get_default_routing_table
from aria_agent.providers.registry import get_default_registry

registry = get_default_sub_agent_registry(get_default_registry(), ModelSelector(get_default_routing_table()))
planner = registry.get("planner")
result = asyncio.run(planner.run("Design a /health endpoint for a FastAPI app"))
print(result.output_text)
```

## See also

- `~/.hermes/skills/software-development/aria-subagents/SKILL.md` — full skill
- `examples/run_subagents_demo.py` — runnable demo (below)
- `docs/architecture.md` — system architecture

## Runnable sub-agent demo

```python
"""Demo: run 4 sub-agents showing parallel + sequential orchestration."""
import asyncio
from aria_agent.subagents import (
    Orchestrator,
    get_default_sub_agent_registry,
)
from aria_agent.router import ModelSelector, get_default_routing_table
from aria_agent.providers.registry import get_default_registry


async def main():
    registry = get_default_sub_agent_registry(
        get_default_registry(), ModelSelector(get_default_routing_table())
    )
    orch = Orchestrator(registry)

    task = "Add a /health endpoint to a FastAPI app that returns service status"

    # Parallel: get planner + architect + researcher views at once
    print("=== PARALLEL: planner + architect + researcher ===")
    parallel = await orch.run_parallel(
        task,
        ["planner", "architect", "researcher"],
    )
    print(f"Mode: {parallel.mode}, steps: {parallel.num_steps}, "
          f"models: {parallel.num_models_used}, cost: ${parallel.total_cost_usd:.4f}")
    for step in parallel.steps:
        print(f"  {step.role.value}: {step.result.model_id} ({step.wall_clock_ms:.0f}ms)")
    print()

    # Sequential: plan → implement → validate
    print("=== SEQUENTIAL: planner → implementer → validator ===")
    sequential = await orch.run_sequential(
        task,
        ["planner", "implementer", "validator"],
    )
    print(f"Mode: {sequential.mode}, steps: {sequential.num_steps}, "
          f"models: {sequential.num_models_used}, cost: ${sequential.total_cost_usd:.4f}")
    for step in sequential.steps:
        print(f"  {step.role.value}: {step.result.model_id} ({step.wall_clock_ms:.0f}ms)")
    print(f"\nFinal output: {sequential.final_output[:200]}...")


if __name__ == "__main__":
    asyncio.run(main())
```
