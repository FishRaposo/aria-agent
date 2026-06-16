"""Database-backed stores for runs, tasks, and approvals.

Each store mirrors the in-memory interface in ``store.py`` exactly, returning
plain dicts so callers never depend on ORM objects. The approval lifecycle
(pending -> approved/rejected/expired with a timeout) is identical to the
in-memory version, reusing :class:`ApprovalStatus` and the expiry rule.
"""

import json
import time
from typing import Any, Dict, List, Optional

from .store import DEFAULT_APPROVAL_TIMEOUT, ApprovalStatus


def _approval_row_to_dict(row) -> Dict[str, Any]:
    now = time.time()
    status = row.status
    if status == ApprovalStatus.PENDING.value and now > row.expires_at:
        status = ApprovalStatus.EXPIRED.value
    return {
        "id": row.id,
        "run_id": row.run_id,
        "action": row.action,
        "parameters": json.loads(row.parameters_json or "{}"),
        "status": status,
        "reason": row.reason,
        "expires_at": row.expires_at,
        "decided_at": row.decided_at,
        "seconds_remaining": max(0.0, round(row.expires_at - now, 2)),
    }


class DatabaseRunStore:
    """Persists ``AgentRun`` rows via a session factory."""

    def __init__(self, session_factory):
        self.session_factory = session_factory

    def _session(self):
        return next(self.session_factory())

    def save(self, run: Dict[str, Any]) -> Dict[str, Any]:
        from .models import AgentRun

        session = self._session()
        try:
            record = AgentRun(
                id=run["id"],
                query=run["query"],
                response=run.get("response"),
                mode=run.get("mode", "free_running"),
                status=run.get("status", "completed"),
                route=run.get("route"),
                trace_json=json.dumps(run.get("trace")),
                cost_json=json.dumps(run.get("cost")),
            )
            session.merge(record)
            session.commit()
        finally:
            session.close()
        return run

    def get(self, run_id: str) -> Optional[Dict[str, Any]]:
        from .models import AgentRun

        session = self._session()
        try:
            row = session.get(AgentRun, run_id)
            if row is None:
                return None
            return self._row_to_dict(row)
        finally:
            session.close()

    def list(self, limit: int = 50) -> List[Dict[str, Any]]:
        from .models import AgentRun

        session = self._session()
        try:
            rows = (
                session.query(AgentRun)
                .order_by(AgentRun.created_at.desc())
                .limit(limit)
                .all()
            )
            return [self._row_to_dict(r) for r in rows]
        finally:
            session.close()

    @staticmethod
    def _row_to_dict(row) -> Dict[str, Any]:
        return {
            "id": row.id,
            "query": row.query,
            "response": row.response,
            "mode": row.mode,
            "status": row.status,
            "route": row.route,
            "trace": json.loads(row.trace_json) if row.trace_json else None,
            "cost": json.loads(row.cost_json) if row.cost_json else None,
            "created_at": row.created_at.timestamp() if row.created_at else 0,
        }


class DatabaseTaskStore:
    """Persists ``CreatedTask`` rows via a session factory."""

    def __init__(self, session_factory):
        self.session_factory = session_factory

    def _session(self):
        return next(self.session_factory())

    def create(self, title: str, description: str) -> Dict[str, Any]:
        from .models import CreatedTask

        session = self._session()
        try:
            task = CreatedTask(title=title, description=description, status="open")
            session.add(task)
            session.commit()
            session.refresh(task)
            return self._row_to_dict(task)
        finally:
            session.close()

    def get(self, task_id: str) -> Optional[Dict[str, Any]]:
        from .models import CreatedTask

        session = self._session()
        try:
            row = session.get(CreatedTask, task_id)
            return self._row_to_dict(row) if row else None
        finally:
            session.close()

    def list(self, limit: int = 50) -> List[Dict[str, Any]]:
        from .models import CreatedTask

        session = self._session()
        try:
            rows = (
                session.query(CreatedTask)
                .order_by(CreatedTask.created_at.desc())
                .limit(limit)
                .all()
            )
            return [self._row_to_dict(r) for r in rows]
        finally:
            session.close()

    @staticmethod
    def _row_to_dict(row) -> Dict[str, Any]:
        return {
            "id": row.id,
            "title": row.title,
            "description": row.description,
            "status": row.status,
            "created_at": row.created_at.timestamp() if row.created_at else 0,
        }


class DatabaseApprovalStore:
    """Persists the approval queue via a session factory."""

    def __init__(self, session_factory, timeout: float = DEFAULT_APPROVAL_TIMEOUT):
        self.session_factory = session_factory
        self._timeout = timeout

    def _session(self):
        return next(self.session_factory())

    def create(
        self,
        action: str,
        parameters: Dict[str, Any],
        run_id: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        from .models import ApprovalRecord

        ttl = self._timeout if timeout is None else timeout
        session = self._session()
        try:
            record = ApprovalRecord(
                run_id=run_id,
                action=action,
                parameters_json=json.dumps(parameters),
                status=ApprovalStatus.PENDING.value,
                expires_at=time.time() + ttl,
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return _approval_row_to_dict(record)
        finally:
            session.close()

    def get(self, approval_id: str) -> Optional[Dict[str, Any]]:
        from .models import ApprovalRecord

        session = self._session()
        try:
            row = session.get(ApprovalRecord, approval_id)
            if row is None:
                return None
            self._persist_expiry(session, row)
            return _approval_row_to_dict(row)
        finally:
            session.close()

    def list(
        self, status: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        from .models import ApprovalRecord

        session = self._session()
        try:
            rows = (
                session.query(ApprovalRecord)
                .order_by(ApprovalRecord.expires_at.desc())
                .all()
            )
            for row in rows:
                self._persist_expiry(session, row)
            dicts = [_approval_row_to_dict(r) for r in rows]
        finally:
            session.close()
        if status:
            dicts = [d for d in dicts if d["status"] == status]
        return dicts[:limit]

    def decide(
        self, approval_id: str, approved: bool, reason: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        from .models import ApprovalRecord

        session = self._session()
        try:
            row = session.get(ApprovalRecord, approval_id)
            if row is None:
                return None
            self._persist_expiry(session, row)
            if row.status == ApprovalStatus.PENDING.value:
                row.status = (
                    ApprovalStatus.APPROVED.value
                    if approved
                    else ApprovalStatus.REJECTED.value
                )
                row.reason = reason
                row.decided_at = time.time()
                session.commit()
                session.refresh(row)
            return _approval_row_to_dict(row)
        finally:
            session.close()

    @staticmethod
    def _persist_expiry(session, row) -> None:
        if row.status == ApprovalStatus.PENDING.value and time.time() > row.expires_at:
            row.status = ApprovalStatus.EXPIRED.value
            row.decided_at = row.expires_at
            session.commit()
