"""Task agent example — persists tasks, free-running mode.

A productivity agent that creates tasks. It runs free-running so the risky
``task_creator`` tool executes directly (no approval pause) and persists each
task into the in-memory task store (or DB when configured).
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from aria.agents import AriaAgent  # noqa: E402
from aria.approvals import ApprovalGate  # noqa: E402
from aria.memory import AgentMemory  # noqa: E402
from aria.routing import build_router  # noqa: E402
from aria.store import InMemoryTaskStore  # noqa: E402
from aria.tools import build_default_registry  # noqa: E402


def build_task_agent(task_store=None):
    task_store = task_store or InMemoryTaskStore()
    registry = build_default_registry(task_store=task_store)
    agent = AriaAgent(
        registry,
        ApprovalGate(enabled=True, mode="free_running"),
        router=build_router("keyword"),
        memory=AgentMemory(),
        mode="free_running",
    )
    return agent, task_store


def main() -> int:
    agent, task_store = build_task_agent()
    for query in (
        "create a task to write the quarterly report",
        "todo: schedule the team offsite",
    ):
        result = agent.run_structured(query)
        print(f"[{result.status}] {result.response}")
    print(f"persisted tasks: {len(task_store.list())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
