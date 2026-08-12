"""Research agent example — safe, free-running, read-only tools.

A research assistant that only uses ``web_search``, ``file_reader``, and
``calculator`` (all SAFE permission). Runs free-running so there are no approval
pauses. Fully offline: web_search returns deterministic mock results.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from aria.agents import AriaAgent  # noqa: E402
from aria.approvals import ApprovalGate  # noqa: E402
from aria.llm_client import AgentLLMClient  # noqa: E402
from aria.memory import AgentMemory  # noqa: E402
from aria.routing import build_router  # noqa: E402
from aria.tools import build_default_registry  # noqa: E402


def build_research_agent() -> AriaAgent:
    registry = build_default_registry()
    return AriaAgent(
        registry,
        ApprovalGate(enabled=True, mode="free_running"),
        router=build_router("auto", llm_client=AgentLLMClient()),
        memory=AgentMemory(),
        mode="free_running",
    )


def main() -> int:
    agent = build_research_agent()
    for query in (
        "search for RAG",
        "look up fastapi",
        "calculate 42 * 1.5",
    ):
        result = agent.run_structured(query)
        print(f"[{result.route}] {query} -> {result.response[:80]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
