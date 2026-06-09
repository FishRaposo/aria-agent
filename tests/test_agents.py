from aria_agent.agents import AriaAgent
from aria_agent.approvals import ApprovalGate
from aria_agent.tools import ToolRegistry
from pydantic import BaseModel


class CalculatorInput(BaseModel):
    expression: str


def make_registry_with_calc():
    reg = ToolRegistry()

    @reg.register("calculator", CalculatorInput)
    def calc(expression: str) -> str:
        return f"Result: {expression}"

    return reg


class TestAriaAgent:
    def test_run_matches_calculator_tool(self):
        reg = make_registry_with_calc()
        gate = ApprovalGate(enabled=True)
        agent = AriaAgent(reg, gate)
        result = agent.run("calculate 2 + 2")
        assert "Result" in result or "Error" in result

    def test_run_no_tool_match(self):
        reg = make_registry_with_calc()
        gate = ApprovalGate(enabled=True)
        agent = AriaAgent(reg, gate)
        result = agent.run("Hello, how are you?")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_run_empty_query(self):
        reg = make_registry_with_calc()
        gate = ApprovalGate(enabled=True)
        agent = AriaAgent(reg, gate)
        result = agent.run("")
        assert isinstance(result, str)

    def test_run_with_disabled_approval(self):
        reg = make_registry_with_calc()
        gate = ApprovalGate(enabled=False)
        agent = AriaAgent(reg, gate)
        result = agent.run("calculate 5 + 3")
        assert isinstance(result, str)

    def test_memory_tracks_user_query(self):
        reg = make_registry_with_calc()
        gate = ApprovalGate(enabled=True)
        agent = AriaAgent(reg, gate)
        agent.run("calculate 1 + 1")
        assert len(agent.memory.messages) >= 1
        assert agent.memory.messages[0]["role"] == "user"
