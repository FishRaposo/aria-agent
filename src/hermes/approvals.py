"""Approval gate — bridges risky tool calls to the approval queue.

Two modes:

* ``free_running`` — the gate auto-approves; risky tools execute directly (still
  logged for audit). This is the offline-first default for the demo and tests.
* ``approval_gated`` — risky tool calls create a *pending* approval in the store
  and the agent pauses, returning the approval id to the caller. A human (or the
  ``/approvals/{id}/approve`` endpoint) must approve before the tool runs.

The gate is backed by an approval store (DB-backed or in-memory) so pending
approvals survive restarts and are visible via the API.
"""

from typing import Any, Dict, Optional

from loguru import logger

from .store import ApprovalStatus, InMemoryApprovalStore


class ApprovalGate:
    """Decides whether a tool call may proceed, creating approvals when gated."""

    def __init__(
        self,
        enabled: bool = True,
        mode: str = "free_running",
        store: Optional[Any] = None,
    ):
        # ``enabled`` retained for backward compatibility: enabled=False bypasses
        # all checks (always approve), matching the original gate semantics.
        self.enabled = enabled
        self.mode = mode
        self.store = store or InMemoryApprovalStore()

    # --- legacy boolean API (kept for existing tests/demos) -----------------
    def request_approval(self, action_name: str, parameters: dict) -> bool:
        """Synchronous boolean decision (free-running / disabled gate)."""
        if not self.enabled:
            return True
        logger.warning("--- SECURITY CHECK: approval for '{}' ---", action_name)
        logger.warning("Parameters: {}", parameters)
        if self.mode == "approval_gated":
            return False
        logger.info("Auto-approved by free-running policy.")
        return True

    # --- queue-backed API used by the agent loop ----------------------------
    def evaluate(
        self,
        action_name: str,
        parameters: Dict[str, Any],
        requires_approval: bool,
        run_id: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Return a decision dict for a tool call.

        Shape: ``{"decision": "approved"|"pending", "approval": <dict-or-None>}``.
        Safe tools, a disabled gate, or free-running mode all yield ``approved``.
        Risky tools under ``approval_gated`` mode create a pending approval.
        """
        if not self.enabled or not requires_approval or self.mode != "approval_gated":
            return {"decision": ApprovalStatus.APPROVED.value, "approval": None}

        logger.warning("--- SECURITY CHECK: queuing approval for '{}' ---", action_name)
        approval = self.store.create(
            action=action_name,
            parameters=parameters,
            run_id=run_id,
            timeout=timeout,
        )
        return {"decision": ApprovalStatus.PENDING.value, "approval": approval}
