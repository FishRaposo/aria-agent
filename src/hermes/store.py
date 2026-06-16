"""In-memory stores for runs, tasks, and approvals.

These are the offline-first defaults used when no database is reachable. Each
class mirrors the interface of its DB-backed counterpart in ``store_db.py`` so
the rest of the app is agnostic to which backend is active. The approval store
implements the full pending -> approved/rejected/expired lifecycle with a
timeout, shared by both backends via ``ApprovalStatus`` and the expiry helper.
"""

import threading
import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional

DEFAULT_APPROVAL_TIMEOUT = 300.0  # seconds


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


def approval_to_dict(record: Dict[str, Any]) -> Dict[str, Any]:
    """Normalise an approval record dict for API responses."""
    now = time.time()
    status = record["status"]
    if status == ApprovalStatus.PENDING.value and now > record["expires_at"]:
        status = ApprovalStatus.EXPIRED.value
    return {
        "id": record["id"],
        "run_id": record.get("run_id"),
        "action": record["action"],
        "parameters": record["parameters"],
        "status": status,
        "reason": record.get("reason"),
        "expires_at": record["expires_at"],
        "decided_at": record.get("decided_at"),
        "seconds_remaining": max(0.0, round(record["expires_at"] - now, 2)),
    }


class InMemoryRunStore:
    """Stores agent run summaries keyed by run id."""

    def __init__(self) -> None:
        self._runs: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def save(self, run: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            self._runs[run["id"]] = run
        return run

    def get(self, run_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            run = self._runs.get(run_id)
            return dict(run) if run else None

    def list(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            runs = sorted(
                self._runs.values(), key=lambda r: r.get("created_at", 0), reverse=True
            )
        return [dict(r) for r in runs[:limit]]


class InMemoryTaskStore:
    """Stores tasks created by the ``task_creator`` tool."""

    def __init__(self) -> None:
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def create(self, title: str, description: str) -> Dict[str, Any]:
        task = {
            "id": uuid.uuid4().hex[:12],
            "title": title,
            "description": description,
            "status": "open",
            "created_at": time.time(),
        }
        with self._lock:
            self._tasks[task["id"]] = task
        return dict(task)

    def get(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            task = self._tasks.get(task_id)
            return dict(task) if task else None

    def list(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            tasks = sorted(
                self._tasks.values(),
                key=lambda t: t.get("created_at", 0),
                reverse=True,
            )
        return [dict(t) for t in tasks[:limit]]


class InMemoryApprovalStore:
    """Pending-approval queue with approve/reject and a timeout."""

    def __init__(self, timeout: float = DEFAULT_APPROVAL_TIMEOUT) -> None:
        self._approvals: Dict[str, Dict[str, Any]] = {}
        self._timeout = timeout
        self._lock = threading.Lock()

    def create(
        self,
        action: str,
        parameters: Dict[str, Any],
        run_id: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        ttl = self._timeout if timeout is None else timeout
        record = {
            "id": uuid.uuid4().hex[:12],
            "run_id": run_id,
            "action": action,
            "parameters": parameters,
            "status": ApprovalStatus.PENDING.value,
            "reason": None,
            "created_at": time.time(),
            "expires_at": time.time() + ttl,
            "decided_at": None,
        }
        with self._lock:
            self._approvals[record["id"]] = record
        return approval_to_dict(record)

    def get(self, approval_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            record = self._approvals.get(approval_id)
            if record is None:
                return None
            self._maybe_expire(record)
            return approval_to_dict(record)

    def list(
        self, status: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        with self._lock:
            records = list(self._approvals.values())
            for record in records:
                self._maybe_expire(record)
        dicts = [approval_to_dict(r) for r in records]
        if status:
            dicts = [d for d in dicts if d["status"] == status]
        dicts.sort(key=lambda d: d["expires_at"], reverse=True)
        return dicts[:limit]

    def decide(
        self, approval_id: str, approved: bool, reason: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        with self._lock:
            record = self._approvals.get(approval_id)
            if record is None:
                return None
            self._maybe_expire(record)
            if record["status"] != ApprovalStatus.PENDING.value:
                # Already decided or expired — return current state, no change.
                return approval_to_dict(record)
            record["status"] = (
                ApprovalStatus.APPROVED.value
                if approved
                else ApprovalStatus.REJECTED.value
            )
            record["reason"] = reason
            record["decided_at"] = time.time()
            return approval_to_dict(record)

    @staticmethod
    def _maybe_expire(record: Dict[str, Any]) -> None:
        if (
            record["status"] == ApprovalStatus.PENDING.value
            and time.time() > record["expires_at"]
        ):
            record["status"] = ApprovalStatus.EXPIRED.value
            record["decided_at"] = record["expires_at"]
