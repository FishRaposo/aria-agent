"""Tests for tool routing — keyword + simulated-LLM, golden decisions."""

import pytest

from aria.costs import CostTracker
from aria.llm_client import AgentLLMClient
from aria.routing import KeywordRouter, LLMRouter, RouteDecision, build_router


class TestKeywordRouter:
    @pytest.mark.parametrize(
        "query,tool",
        [
            ("calculate 2 + 2", "calculator"),
            ("what is 12 * 4", "calculator"),
            ("search for python", "web_search"),
            ("look up the weather", "web_search"),
            ("read the file notes.txt", "file_reader"),
            ("create a task to ship it", "task_creator"),
            ("todo: buy milk", "task_creator"),
            ("draft an email to a@b.com", "email_draft"),
        ],
    )
    def test_golden_routes(self, query, tool):
        decision = KeywordRouter().route(query)
        assert decision.tool == tool

    def test_no_match_returns_none(self):
        decision = KeywordRouter().route("hello, how are you today?")
        assert decision.tool is None
        assert not decision.is_tool

    def test_task_before_file_when_ambiguous(self):
        # "file" appears but task intent should win.
        decision = KeywordRouter().route("create a task to file the report")
        assert decision.tool == "task_creator"

    def test_calculator_extracts_expression(self):
        decision = KeywordRouter().route("please calculate 120 + 350")
        assert decision.arguments["expression"] == "120 + 350"

    def test_email_extracts_recipient(self):
        decision = KeywordRouter().route("draft an email to legal@example.com")
        assert decision.arguments["recipient"] == "legal@example.com"


class TestLLMRouter:
    def test_simulated_routing_matches_keyword(self):
        router = LLMRouter(llm_client=AgentLLMClient(), simulate=True)
        decision = router.route("calculate 5 + 5")
        assert decision.tool == "calculator"
        assert decision.strategy == "llm"

    def test_records_cost(self):
        router = LLMRouter(llm_client=AgentLLMClient(), simulate=True)
        tracker = CostTracker()
        router.route("search for rag", cost_tracker=tracker)
        assert tracker.summary()["total_calls"] >= 1

    def test_rejects_hallucinated_tool(self):
        router = LLMRouter(llm_client=AgentLLMClient(), simulate=True)
        # Parser must drop unknown tools and fall back to keyword routing.
        decision = router._parse('{"tool": "rm_rf", "arguments": {}}')
        assert decision is None

    def test_parse_invalid_json(self):
        router = LLMRouter(simulate=False)
        assert router._parse("not json") is None
        assert router._parse(None) is None

    def test_falls_back_to_keyword_on_no_client(self):
        # No client, no simulation -> keyword fallback path.
        router = LLMRouter(llm_client=None, simulate=False)
        decision = router.route("calculate 1 + 1")
        assert decision.tool == "calculator"
        assert decision.strategy == "keyword_fallback"

    def test_fallback_on_client_exception(self):
        class BoomClient:
            def generate(self, *a, **k):
                raise RuntimeError("boom")

        router = LLMRouter(llm_client=BoomClient(), simulate=True)
        decision = router.route("calculate 9 + 1")
        # Falls back to keyword routing rather than crashing.
        assert decision.tool == "calculator"


class TestBuildRouter:
    def test_build_keyword(self):
        assert isinstance(build_router("keyword"), KeywordRouter)

    def test_build_auto_is_llm(self):
        assert isinstance(build_router("auto"), LLMRouter)

    def test_route_decision_dataclass(self):
        d = RouteDecision(tool="calculator", arguments={"expression": "1+1"})
        assert d.is_tool is True
