"""ARIA conversation memory — persistent (DB) with in-memory fallback.

``AgentMemory`` keeps the original simple in-memory list API (used directly in
unit tests and the demo). ``PersistentMemory`` implements the same surface but
reads/writes ``MemoryMessage`` rows through a session factory, so conversation
history survives restarts. ``get_memory()`` picks the backend based on the DB
availability probe, mirroring the offline-first default.
"""

import threading
from typing import Dict, List, Optional

_DEFAULT_SESSION = "default"


class AgentMemory:
    """In-memory message list with a sliding context window."""

    def __init__(self, session_id: str = _DEFAULT_SESSION, max_messages: int = 50):
        self.session_id = session_id
        self.max_messages = max_messages
        self.messages: List[Dict[str, str]] = []
        self._lock = threading.RLock()
        self._event_keys: set[str] = set()

    def add_message(self, role: str, content: str) -> None:
        with self._lock:
            self.messages.append({"role": role, "content": content})
            if len(self.messages) > self.max_messages:
                self.messages = self.messages[-self.max_messages :]

    def add_message_once(self, role: str, content: str, event_key: str) -> bool:
        """Append a reconciliation event once, including after context trimming."""
        with self._lock:
            if event_key in self._event_keys:
                return False
            self.add_message(role, content)
            self._event_keys.add(event_key)
            return True

    def get_context(self, limit: Optional[int] = None) -> List[Dict[str, str]]:
        with self._lock:
            messages = self.messages if limit is None else self.messages[-limit:]
            return [dict(message) for message in messages]

    def clear(self) -> None:
        with self._lock:
            self.messages = []
            self._event_keys.clear()


class PersistentMemory:
    """DB-backed memory mirroring the :class:`AgentMemory` API.

    Loads existing rows for the session on construction so multi-turn context
    survives restarts; appends are written through immediately.
    """

    def __init__(
        self,
        session_factory,
        session_id: str = _DEFAULT_SESSION,
        max_messages: int = 50,
    ):
        self.session_factory = session_factory
        self.session_id = session_id
        self.max_messages = max_messages

    def _session(self):
        return next(self.session_factory())

    def add_message(self, role: str, content: str) -> None:
        self._append(role, content)

    def add_message_once(self, role: str, content: str, event_key: str) -> bool:
        return self._append(role, content, event_key=f"{self.session_id}:{event_key}")

    def _append(self, role: str, content: str, event_key: Optional[str] = None) -> bool:
        from sqlalchemy import func
        from sqlalchemy.exc import IntegrityError

        from .models import MemoryMessage

        session = self._session()
        try:
            previous = (
                session.query(func.max(MemoryMessage.seq))
                .filter(MemoryMessage.session_id == self.session_id)
                .scalar()
            )
            session.add(
                MemoryMessage(
                    session_id=self.session_id,
                    role=role,
                    content=content,
                    seq=0 if previous is None else previous + 1,
                    event_key=event_key,
                )
            )
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                if (
                    event_key is None
                    or not session.query(MemoryMessage)
                    .filter(MemoryMessage.event_key == event_key)
                    .first()
                ):
                    raise
                return False
            return True
        finally:
            session.close()

    def get_context(self, limit: Optional[int] = None) -> List[Dict[str, str]]:
        from .models import MemoryMessage

        session = self._session()
        try:
            query = (
                session.query(MemoryMessage)
                .filter(MemoryMessage.session_id == self.session_id)
                .order_by(
                    MemoryMessage.seq.desc(),
                    MemoryMessage.created_at.desc(),
                    MemoryMessage.id.desc(),
                )
                .limit(self.max_messages if limit is None else limit)
            )
            rows = list(reversed(query.all()))
        finally:
            session.close()
        messages = [{"role": r.role, "content": r.content} for r in rows]
        if limit is not None:
            return messages[-limit:]
        return messages[-self.max_messages :]

    @property
    def messages(self) -> List[Dict[str, str]]:
        return self.get_context()

    def clear(self) -> None:
        from .models import MemoryMessage

        session = self._session()
        try:
            session.query(MemoryMessage).filter(
                MemoryMessage.session_id == self.session_id
            ).delete()
            session.commit()
        finally:
            session.close()


def get_memory(session_id: str = _DEFAULT_SESSION):
    """Return DB-backed memory when available, else an in-memory store."""
    from . import db as db_module

    if db_module.db_available and db_module.db_manager is not None:
        return PersistentMemory(db_module.db_manager.get_session, session_id=session_id)
    return AgentMemory(session_id=session_id)
