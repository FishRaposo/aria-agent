"""Optional local approval-expiry sweep compatible with both store backends."""

from __future__ import annotations

from typing import Any


class ApprovalSweeper:
    """Materialize expired approvals without requiring Celery or Redis."""

    def __init__(self, store: Any) -> None:
        self.store = store

    def sweep(self) -> dict[str, int]:
        after = self.store.list()
        return {
            "checked": len(after),
            "expired": sum(1 for approval in after if approval["status"] == "expired"),
        }
