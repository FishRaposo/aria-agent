from aria_agent.memory import AgentMemory


class TestAgentMemory:
    def test_add_message_stores_role_and_content(self):
        memory = AgentMemory()
        memory.add_message("user", "Hello")
        assert len(memory.messages) == 1
        assert memory.messages[0]["role"] == "user"
        assert memory.messages[0]["content"] == "Hello"

    def test_get_context_returns_all_messages(self):
        memory = AgentMemory()
        memory.add_message("user", "Q1")
        memory.add_message("system", "R1")
        memory.add_message("user", "Q2")
        context = memory.get_context()
        assert len(context) == 3
        assert context[1]["role"] == "system"

    def test_empty_memory(self):
        memory = AgentMemory()
        assert memory.get_context() == []

    def test_system_messages_tracked(self):
        memory = AgentMemory()
        memory.add_message("system", "Tool result: 42")
        ctx = memory.get_context()
        assert ctx[0]["role"] == "system"
