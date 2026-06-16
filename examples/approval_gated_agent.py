"""Approval-gated agent example — risky tools pause for human sign-off.

Runs in ``approval_gated`` mode: any ``requires_approval`` tool (task_creator,
email_draft) creates a *pending* approval and the run pauses. The example then
demonstrates both the approve-and-execute path and the reject path against the
shared approval store.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from hermes.agents import HermesAgent  # noqa: E402
from hermes.approvals import ApprovalGate  # noqa: E402
from hermes.memory import AgentMemory  # noqa: E402
from hermes.routing import build_router  # noqa: E402
from hermes.store import InMemoryApprovalStore, InMemoryTaskStore  # noqa: E402
from hermes.tools import build_default_registry  # noqa: E402


def build_approval_gated_agent():
    task_store = InMemoryTaskStore()
    approval_store = InMemoryApprovalStore()
    registry = build_default_registry(task_store=task_store)
    agent = HermesAgent(
        registry,
        ApprovalGate(enabled=True, mode="approval_gated", store=approval_store),
        router=build_router("keyword"),
        memory=AgentMemory(),
        mode="approval_gated",
    )
    return agent, approval_store, task_store


def main() -> int:
    agent, approval_store, task_store = build_approval_gated_agent()

    # Risky tool -> pending approval.
    pending = agent.run_structured("create a task to file the compliance report")
    print(f"status={pending.status}, approval={pending.approval['id']}")
    assert pending.status == "pending_approval"

    # Approve and execute.
    approval_store.decide(pending.approval["id"], approved=True, reason="ok")
    decided = approval_store.get(pending.approval["id"])
    output = agent.execute_approved(decided["action"], decided["parameters"])
    print(f"approved -> {output}")
    print(f"tasks persisted: {len(task_store.list())}")

    # Reject path.
    rejected_run = agent.run_structured("draft an email to legal@example.com")
    rec = approval_store.decide(
        rejected_run.approval["id"], approved=False, reason="needs revision"
    )
    print(f"rejected -> {rec['status']} ({rec['reason']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
