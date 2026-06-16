"""Conversation memory — persistent (DB) with in-memory fallback.

``AgentMemory`` keeps the original simple in-memory list API (used directly in
unit tests and the demo). ``PersistentMemory`` implements the same surface but
reads/writes ``MemoryMessage`` rows through a session factory, so conversation
history survives restarts. ``get_memory()`` picks the backend based on the DB
availability probe, mirroring the offline-first default.
"""

from typing import Dict, List, Optional

_DEFAULT_SESSION = "default"


class AgentMemory:
    """In-memory message list with a sliding context window."""

    def __init__(self, session_id: str = _DEFAULT_SESSION, max_messages: int = 50):
        self.session_id = session_id
        self.max_messages = max_messages
        self.messages: List[Dict[str, str]] = []

    def add_message(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})
        # Bound growth so context never explodes past max_messages.
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages :]

    def get_context(self, limit: Optional[int] = None) -> List[Dict[str, str]]:
        if limit is None:
            return list(self.messages)
        return list(self.messages[-limit:])

    def clear(self) -> None:
        self.messages = []


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
        from .models import MemoryMessage

        session = self._session()
        try:
            count = (
                session.query(MemoryMessage)
                .filter(MemoryMessage.session_id == self.session_id)
                .count()
            )
            session.add(
                MemoryMessage(
                    session_id=self.session_id,
                    role=role,
                    content=content,
                    seq=count,
                )
            )
            session.commit()
        finally:
            session.close()

    def get_context(self, limit: Optional[int] = None) -> List[Dict[str, str]]:
        from .models import MemoryMessage

        session = self._session()
        try:
            query = (
                session.query(MemoryMessage)
                .filter(MemoryMessage.session_id == self.session_id)
                .order_by(MemoryMessage.seq.asc())
            )
            rows = query.all()
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
