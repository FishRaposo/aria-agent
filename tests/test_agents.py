"""Tests for the v0.1 KeywordRouterAgent (preserved).

Originally written for v0.1's `AriaAgent` class. The class was renamed to
`KeywordRouterAgent` in v0.3 to free up the name for the new orchestrator.
The legacy `AriaAgent` import still works (it's an alias) so v0.1 callers
don't break.

The test logic is identical to the v0.1 version — we're checking that the
preserved behavior still works after the rename and the v0.3 integration.
"""
import pytest

from aria_agent.agents import KeywordRouterAgent, AriaAgent
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


class TestKeywordRouterAgent:
    def test_run_matches_calculator_tool(self):
        reg = make_registry_with_calc()
        gate = ApprovalGate(enabled=True)
        agent = KeywordRouterAgent(reg, gate)
        result = agent.run("calculate 2 + 2")
        assert "Result" in result or "Error" in result

    def test_run_no_tool_match(self):
        reg = make_registry_with_calc()
        gate = ApprovalGate(enabled=True)
        agent = KeywordRouterAgent(reg, gate)
        result = agent.run("Hello, how are you?")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_run_empty_query(self):
        reg = make_registry_with_calc()
        gate = ApprovalGate(enabled=True)
        agent = KeywordRouterAgent(reg, gate)
        result = agent.run("")
        assert isinstance(result, str)

    def test_run_with_disabled_approval(self):
        reg = make_registry_with_calc()
        gate = ApprovalGate(enabled=False)
        agent = KeywordRouterAgent(reg, gate)
        result = agent.run("calculate 5 + 3")
        assert isinstance(result, str)

    def test_memory_tracks_user_query(self):
        reg = make_registry_with_calc()
        gate = ApprovalGate(enabled=True)
        agent = KeywordRouterAgent(reg, gate)
        agent.run("calculate 1 + 1")
        assert len(agent.memory.messages) >= 1
        assert agent.memory.messages[0]["role"] == "user"


class TestAriaAgentBackwardsCompat:
    """The v0.1 name `AriaAgent` should still work as an alias."""

    def test_aria_agent_alias_is_keyword_router(self):
        """AriaAgent is an alias for KeywordRouterAgent."""
        assert AriaAgent is KeywordRouterAgent

    def test_can_instantiate_via_alias(self):
        reg = make_registry_with_calc()
        gate = ApprovalGate(enabled=True)
        # Old code uses: AriaAgent(registry, gate)
        agent = AriaAgent(reg, gate)
        result = agent.run("calculate 2 + 2")
        assert "Result" in result or "Error" in result
