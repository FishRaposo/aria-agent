"""Memory tests — in-memory and persistent (DB) backends."""

from hermes.memory import AgentMemory, PersistentMemory


class TestAgentMemory:
    def test_add_and_get(self):
        m = AgentMemory()
        m.add_message("user", "Hello")
        assert m.get_context()[0] == {"role": "user", "content": "Hello"}

    def test_context_ordering(self):
        m = AgentMemory()
        m.add_message("user", "Q1")
        m.add_message("system", "R1")
        ctx = m.get_context()
        assert [c["role"] for c in ctx] == ["user", "system"]

    def test_limit_returns_tail(self):
        m = AgentMemory()
        for i in range(10):
            m.add_message("user", str(i))
        assert m.get_context(limit=3) == [
            {"role": "user", "content": "7"},
            {"role": "user", "content": "8"},
            {"role": "user", "content": "9"},
        ]

    def test_sliding_window_bounds_growth(self):
        m = AgentMemory(max_messages=5)
        for i in range(20):
            m.add_message("user", str(i))
        assert len(m.messages) == 5
        assert m.messages[-1]["content"] == "19"

    def test_clear(self):
        m = AgentMemory()
        m.add_message("user", "x")
        m.clear()
        assert m.get_context() == []


class TestPersistentMemory:
    def test_persists_and_reloads(self, mock_db):
        mem = PersistentMemory(mock_db.get_session, session_id="s1")
        mem.add_message("user", "hello")
        mem.add_message("system", "world")
        # Fresh instance over the same DB sees prior history (survives restart).
        reopened = PersistentMemory(mock_db.get_session, session_id="s1")
        ctx = reopened.get_context()
        assert [c["content"] for c in ctx] == ["hello", "world"]

    def test_sessions_are_isolated(self, mock_db):
        a = PersistentMemory(mock_db.get_session, session_id="a")
        b = PersistentMemory(mock_db.get_session, session_id="b")
        a.add_message("user", "only-a")
        assert a.get_context()[0]["content"] == "only-a"
        assert b.get_context() == []

    def test_clear(self, mock_db):
        mem = PersistentMemory(mock_db.get_session, session_id="c")
        mem.add_message("user", "x")
        mem.clear()
        assert mem.get_context() == []

    def test_messages_property(self, mock_db):
        mem = PersistentMemory(mock_db.get_session, session_id="d")
        mem.add_message("user", "hi")
        assert mem.messages[0]["role"] == "user"
