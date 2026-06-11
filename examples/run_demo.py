"""Runnable demo: show Aria Agent routing a real task through live APIs.

Demonstrates BOTH paths in v0.3:

1. **Tool path** (v0.1 KeywordRouterAgent, preserved) — for queries matching
   a tool keyword. Fast, deterministic, no LLM cost.
2. **Model path** (v0.2 router + cooperation pattern) — for everything else.
   LLM-backed, with cost/latency tracking.

Prereqs:
- OPENCODE_GO_API_KEY in the env (the user's OCG Bearer token)
- Aria Agent installed (or PYTHONPATH pointing at src + operator-shared-core/src)

Usage:
    python examples/run_demo.py

What it does:
1. Boots the routing table + provider registry + tool registry
2. Previews the route for 3 model-path tasks
3. Previews the intent for 3 tool-path tasks
4. Runs each through the appropriate path
5. Prints the final output, steps, cost, and intent
"""
import asyncio
import os
import sys

# Make the package importable without installing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "operator-shared-core", "src"))

from aria_agent import AriaAgent, ModelSelector, get_default_registry, get_default_routing_table
from aria_agent.approvals import ApprovalGate
from aria_agent.builtin_tools.calculator import CalculatorInput, calculator
from aria_agent.builtin_tools.email_draft import EmailDraftInput, email_draft
from aria_agent.builtin_tools.file_reader import FileReaderInput, file_reader
from aria_agent.builtin_tools.task_creator import TaskCreatorInput, task_creator
from aria_agent.builtin_tools.web_search import WebSearchInput, web_search
from aria_agent.tools import ToolRegistry


def build_tool_registry() -> ToolRegistry:
    """Build the v0.1 tool registry with the 5 builtin tools (preserved)."""
    reg = ToolRegistry()
    reg.register("calculator", CalculatorInput)(calculator)
    reg.register("web_search", WebSearchInput)(web_search)
    reg.register("file_reader", FileReaderInput)(file_reader)
    reg.register("task_creator", TaskCreatorInput)(task_creator)
    reg.register("email_draft", EmailDraftInput)(email_draft)
    return reg


async def main():
    if not os.environ.get("OPENCODE_GO_API_KEY"):
        print("ERROR: OPENCODE_GO_API_KEY is not set. Export it and try again.")
        sys.exit(1)

    registry = get_default_registry()
    if not registry.list_providers():
        print("ERROR: No providers registered. Check your API keys.")
        sys.exit(1)

    print(f"Registered providers: {registry.list_providers()}")
    print(f"Version: Aria Agent 0.3.0 (v0.1 tools + v0.2 router/cooperation)\n")

    # Build the v0.3 AriaAgent with both paths wired
    tool_registry = build_tool_registry()
    agent = AriaAgent(
        registry=registry,
        router=ModelSelector(get_default_routing_table()),
        tool_registry=tool_registry,
        approval_gate=ApprovalGate(enabled=True),
    )

    # 6 tasks: 3 model-path, 3 tool-path
    model_tasks = [
        ("Quick Q&A", "What is the capital of France?"),
        ("Translation", "Translate 'hello world' to Portuguese"),
        ("Coding", "Write a Python one-liner that returns the sum of a list of numbers"),
    ]
    tool_tasks = [
        ("Calculator (tool path)", "calculate 7 * 6"),
        ("Calculator with no digits (model path)", "calculate the impact of AI on jobs"),
        ("File reader (tool path)", 'read the file "README.md"'),
    ]

    # ---- Model path tasks (v0.2 router + cascade cooperation) -------------
    for label, task in model_tasks:
        print(f"\n{'=' * 60}")
        print(f"MODEL TASK: {label}")
        print(f"  {task}")
        print(f"{'=' * 60}")

        # Preview the intent (which path will run)
        intent = agent.classify_intent(task)
        print(f"\nIntent: {intent.intent.value} ({intent.reason})")

        # Preview the route
        preview = agent.preview_route(task)
        print(f"\nRouting decision:")
        print(f"  Type: {preview['task_type']}")
        print(f"  Primary: {preview['primary']['provider']}/{preview['primary']['model_id']} "
              f"(tier={preview['primary']['tier']})")
        if preview['fallback']:
            print(f"  Fallback: {preview['fallback']['provider']}/{preview['fallback']['model_id']}")
        if preview['escalation']:
            print(f"  Escalation: {preview['escalation']['provider']}/{preview['escalation']['model_id']}")
        print(f"  Reason: {preview['reason']}")

        # Run the cascade pattern
        print(f"\nRunning cascade pattern...")
        result = await agent.run(task, pattern="cascade")
        print(f"\nResult:")
        print(f"  Pattern: {result.pattern}")
        print(f"  Intent: {result.metadata.get('intent', 'n/a')}")
        print(f"  Steps: {result.num_steps}")
        print(f"  Models used: {result.num_models_used}")
        print(f"  Cost: ${result.total_cost_usd:.6f}")
        print(f"  Latency: {result.total_latency_ms:.1f}ms")
        print(f"  Outcome: {result.metadata.get('cascade_outcome', 'n/a')}")
        print(f"\nOutput:\n  {result.final_output}")

    # ---- Tool path tasks (v0.1 KeywordRouterAgent, preserved) -------------
    for label, task in tool_tasks:
        print(f"\n{'=' * 60}")
        print(f"TOOL TASK: {label}")
        print(f"  {task}")
        print(f"{'=' * 60}")

        # Preview the intent
        intent = agent.classify_intent(task)
        print(f"\nIntent: {intent.intent.value}")
        if intent.matched_tool:
            print(f"  Matched tool: {intent.matched_tool} (keyword: '{intent.matched_keyword}')")
        print(f"  Reason: {intent.reason}")

        # Run the agent (auto-dispatches to tool path)
        result = await agent.run(task)
        print(f"\nResult:")
        print(f"  Pattern: {result.pattern}")
        print(f"  Intent: {result.metadata.get('intent', 'n/a')}")
        print(f"  Steps: {result.num_steps}")
        print(f"  Cost: ${result.total_cost_usd:.6f}")
        print(f"  Latency: {result.total_latency_ms:.1f}ms")
        if "matched_tool" in result.metadata:
            print(f"  Matched tool: {result.metadata['matched_tool']}")
        print(f"\nOutput:\n  {result.final_output}")


if __name__ == "__main__":
    asyncio.run(main())
