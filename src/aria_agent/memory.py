"""AgentMemory — in-memory conversation history (v0.1, preserved).

Stores messages as `(role, content)` pairs (well, dicts with role+content).
Provides `add_message`, `get_context`, and a few helpers.

This module was referenced in v0.1 by `agents.py` and `worker.py` but
was not in the original git commit (only the class was inlined in v0.1's
`agents.py`). We define it as a standalone module here so the
KeywordRouterAgent can keep its v0.1 memory semantics in v0.3.

If you wire Aria to a real DB later, swap this out for a persistent
implementation. The contract is:
- `add_message(role, content)` — append a message
- `get_context(n=None)` — return the last `n` messages (default: all)
- `messages` — the underlying list (read-only by convention)
- `clear()` — wipe history
"""
from typing import List, Dict, Optional


class AgentMemory:
    """Per-agent conversation history. v0.1 design, kept intact in v0.3."""

    def __init__(self, max_messages: int = 100):
        self.messages: List[Dict[str, str]] = []
        self.max_messages = max_messages

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the history. Trims oldest if over max_messages."""
        self.messages.append({"role": role, "content": content})
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages:]

    def get_context(self, n: Optional[int] = None) -> List[Dict[str, str]]:
        """Return the last `n` messages (or all if n is None)."""
        if n is None:
            return list(self.messages)
        return list(self.messages[-n:])

    def clear(self) -> None:
        """Wipe the history."""
        self.messages = []

    def __len__(self) -> int:
        return len(self.messages)


__all__ = ["AgentMemory"]
