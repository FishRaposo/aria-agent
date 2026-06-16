"""End-to-end Hermes agent demo — offline, no keys, no database.

Exercises the full framework: keyword + simulated-LLM routing, every builtin
tool, free-running vs approval-gated modes, the approval queue (pending ->
approve -> execute), persistent-or-in-memory stores, cost tracking, and
AgentTrace-compatible span emission. Exits 0 on success.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from hermes.agents import HermesAgent  # noqa: E402
from hermes.approvals import ApprovalGate  # noqa: E402
from hermes.llm_client import AgentLLMClient  # noqa: E402
from hermes.memory import AgentMemory  # noqa: E402
from hermes.routing import build_router  # noqa: E402
from hermes.store import InMemoryApprovalStore, InMemoryTaskStore  # noqa: E402
from hermes.tools import build_default_registry  # noqa: E402


def _print_run(label, result):
    print(f"\n=== {label} ===")
    print(f"  query   : {result.query}")
    print(f"  route   : {result.route}")
    print(f"  status  : {result.status}")
    print(f"  response: {result.response}")
    print(
        f"  trace   : {result.trace['total_steps']} steps, "
        f"{len(result.trace['spans'])} spans, trace_id={result.trace['trace_id'][:8]}"
    )
    print(
        f"  cost    : ${result.cost['total_cost']:.6f} over "
        f"{result.cost['total_calls']} LLM call(s)"
    )


def main() -> int:
    print("--- Running Hermes Agent Framework Demo ---")

    task_store = InMemoryTaskStore()
    approval_store = InMemoryApprovalStore()
    registry = build_default_registry(task_store=task_store)

    # Simulated-LLM router (deterministic, no keys) with keyword fallback.
    router = build_router("auto", llm_client=AgentLLMClient())

    # 1) Free-running agent runs safe + risky tools directly.
    free_agent = HermesAgent(
        registry,
        ApprovalGate(enabled=True, mode="free_running", store=approval_store),
        router=router,
        memory=AgentMemory(),
        mode="free_running",
    )
    _print_run(
        "Calculator (safe, free-running)",
        free_agent.run_structured("Please calculate 120 + 350"),
    )
    _print_run("Web search (safe)", free_agent.run_structured("search for python"))
    _print_run(
        "File reader (sandboxed)", free_agent.run_structured("read the file notes.txt")
    )

    # 2) Approval-gated agent: a risky tool (task_creator) pauses for approval.
    gated_agent = HermesAgent(
        registry,
        ApprovalGate(enabled=True, mode="approval_gated", store=approval_store),
        router=router,
        memory=AgentMemory(),
        mode="approval_gated",
    )
    gated = gated_agent.run_structured("create a task to review the design doc")
    _print_run("Task creator (risky, approval-gated)", gated)
    assert gated.status == "pending_approval", gated.status
    approval_id = gated.approval["id"]
    print(f"\n  -> pending approval {approval_id} created")

    # 3) Approve it out-of-band and execute the tool.
    approval_store.decide(approval_id, approved=True, reason="looks good")
    decided = approval_store.get(approval_id)
    print(f"  -> approval now: {decided['status']}")
    output = gated_agent.execute_approved(decided["action"], decided["parameters"])
    print(f"  -> tool executed: {output}")
    print(f"  -> tasks persisted: {len(task_store.list())}")

    # 4) Reject path on a fresh approval.
    gated2 = gated_agent.run_structured("draft an email to the team about the launch")
    rejected = approval_store.decide(
        gated2.approval["id"], approved=False, reason="too soon"
    )
    print(f"\n  -> rejected approval: {rejected['status']} ({rejected['reason']})")

    # Final assertions so the demo fails loudly if behaviour regresses.
    runs_ok = "470" in free_agent.run_structured("calculate 120 + 350").response
    assert runs_ok, "calculator routing/exec regressed"
    print("\nAgent Final Output: I calculated the value to be 470.")
    print("--- Demo complete (all assertions passed) ---")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
