"""Tests for the AriaAgent (orchestrator) and FastAPI gateway."""
import asyncio
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "operator-shared-core", "src"))


# Reuse the FakeProvider / FakeRegistry from test_cooperation
sys.path.insert(0, os.path.dirname(__file__))
from test_cooperation import FakeProvider, FakeRegistry  # noqa: E402


class TestAriaAgent:
    @pytest.fixture
    def agent(self):
        from aria_agent.agent import AriaAgent
        from aria_agent.router import ModelSelector, get_default_routing_table

        registry = FakeRegistry({
            "opencode-go": FakeProvider("opencode-go", ["Generic answer with enough detail."]),
            "minimax-direct": FakeProvider("minimax-direct", ["M3 answer with enough detail."]),
        })
        return AriaAgent(registry, ModelSelector(get_default_routing_table()))

    def test_list_patterns(self, agent):
        patterns = agent.list_patterns()
        assert "cascade" in patterns
        assert "plan_execute_validate" in patterns
        assert "ensemble" in patterns

    def test_default_pattern_is_cascade(self, agent):
        from aria_agent.cooperation import CascadePattern

        assert agent.default_pattern == "cascade"
        pat = agent.get_pattern()
        assert isinstance(pat, CascadePattern)

    def test_get_pattern_caches(self, agent):
        pat1 = agent.get_pattern("cascade")
        pat2 = agent.get_pattern("cascade")
        assert pat1 is pat2, "Pattern should be cached on the agent"

    def test_get_unknown_pattern_raises(self, agent):
        with pytest.raises(ValueError) as exc:
            agent.get_pattern("nonexistent")
        assert "nonexistent" in str(exc.value)

    def test_run_with_default_pattern(self, agent):
        result = asyncio.run(agent.run("Write a Python function to add two numbers"))
        assert result.pattern == "cascade"
        assert result.final_output

    def test_run_with_explicit_pattern(self, agent):
        result = asyncio.run(agent.run(
            "Write a Python function",
            pattern="plan_execute_validate",
        ))
        assert result.pattern == "plan_execute_validate"

    def test_preview_route(self, agent):
        preview = agent.preview_route("Translate to Portuguese")
        assert "task_type" in preview
        assert "primary" in preview
        assert preview["primary"]["model_id"]


class TestFastAPIGateway:
    """Test the FastAPI endpoints using TestClient (no live API calls)."""

    @pytest.fixture
    def client(self):
        # Skip the gateway tests if loguru (a shared-core dep) isn't installed
        # in this venv. We test the gateway separately when the env is ready.
        try:
            import loguru  # noqa: F401
        except ImportError:
            pytest.skip("loguru not installed; gateway tests need shared-core deps")

        # Override env to ensure OPENCODE_GO_API_KEY is set for the registry
        with patch.dict(
            os.environ,
            {"OPENCODE_GO_API_KEY": "fake-key", "MiniMax_API_KEY": "fake-key"},
        ):
            from aria_agent.providers.registry import reset_default_registry
            from aria_agent.router.routing_table import reset_default_routing_table

            reset_default_registry()
            reset_default_routing_table()

            from fastapi.testclient import TestClient
            # Need to reload main since it captured the registry at import time
            import importlib
            import aria_agent.main
            importlib.reload(aria_agent.main)
            with TestClient(aria_agent.main.app) as c:
                yield c

            reset_default_registry()
            reset_default_routing_table()

    def test_health_endpoint(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "aria-agent"
        assert data["version"] == "0.4.0"
        assert "patterns_available" in data
        assert "tools_available" in data
        assert "subagents_available" in data  # v0.4 added: shows sub-agent role count

    def test_list_subagents(self, client):
        """v0.4 added: /subagents lists all roles + their default model picks."""
        resp = client.get("/subagents")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 9  # 9 roles: planner, architect, implementer, ...
        role_names = {s["role"] for s in data["subagents"]}
        assert "planner" in role_names
        assert "implementer" in role_names
        assert "debugger" in role_names
        assert "documenter" in role_names
        # Each role has a default model picked
        planner = next(s for s in data["subagents"] if s["role"] == "planner")
        assert "default_model" in planner
        assert "model_id" in planner["default_model"]

    def test_list_tools(self, client):
        """v0.3 added: /agent/tools lists the v0.1 builtin tools."""
        resp = client.get("/agent/tools")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 5  # calculator, web_search, file_reader, task_creator, email_draft
        tool_names = {t["name"] for t in data["tools"]}
        assert tool_names == {"calculator", "web_search", "file_reader", "task_creator", "email_draft"}

    def test_intent_preview(self, client):
        """v0.3 added: /agent/intent previews which path would run."""
        # "calculate 2 + 2" should match the calculator tool
        resp = client.post("/agent/intent", json={"task": "calculate 2 + 2"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["intent"] == "tool_call"
        assert data["matched_tool"] == "calculator"

        # "What is the capital of France?" should NOT match any tool
        resp = client.post("/agent/intent", json={"task": "What is the capital of France?"})
        data = resp.json()
        assert data["intent"] == "model_call"
        assert data["matched_tool"] is None

    def test_list_patterns(self, client):
        resp = client.get("/agent/patterns")
        assert resp.status_code == 200
        data = resp.json()
        assert "cascade" in data["patterns"]
        assert "plan_execute_validate" in data["patterns"]
        assert "ensemble" in data["patterns"]
        assert data["default"] == "cascade"

    def test_list_models(self, client):
        resp = client.get("/models")
        assert resp.status_code == 200
        data = resp.json()
        # Total includes both active (callable) and Pro+ (catalog-only) models.
        # Was 12 in the previous routing table; added minimax-m3 (OCG mirror)
        # and gpt-5.4-mini (Codex OAuth) for the M3 chain.
        assert data["total_models"] >= 13
        assert data["active_pool_size"] == 8
        # By-provider breakdown
        assert "opencode-go" in data["by_provider"]
        assert "minimax-direct" in data["by_provider"]

    def test_list_providers(self, client):
        resp = client.get("/providers")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 2
        names = {p["name"] for p in data["providers"]}
        assert "opencode-go" in names
        assert "minimax-direct" in names

    def test_route_preview(self, client):
        resp = client.post("/agent/route", json={"task": "Translate this to Portuguese"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_type"] == "translation"
        assert data["primary"]["model_id"] == "kimi-k2.6"

    def test_run_rejects_empty_task(self, client):
        resp = client.post("/agent/run", json={"task": ""})
        assert resp.status_code == 422  # Pydantic validation
        # Or it might be 400 if it passes the schema but fails the empty check
        # Either way, not 200

    def test_run_rejects_unknown_pattern(self, client):
        resp = client.post(
            "/agent/run",
            json={"task": "test", "pattern": "nonexistent"},
        )
        assert resp.status_code == 400
        assert "Unknown pattern" in resp.json()["detail"]

    def test_run_with_real_ocg_key_calls_live_api(self, client):
        """End-to-end with a real OCG call (using the Hermes-shared key)."""
        # This test only runs if OPENCODE_GO_API_KEY is the real key
        # (the fixture uses "fake-key" which won't work, so this is normally skipped)
        import os
        if os.environ.get("OPENCODE_GO_API_KEY", "").startswith("fake"):
            pytest.skip("Requires real OPENCODE_GO_API_KEY")

        resp = client.post(
            "/agent/run",
            json={"task": "What is 2+2?", "pattern": "cascade"},
        )
        # May be 200 (succeeded) or 500 (provider error) — either is OK
        # for a live test, we just want the gateway plumbing to work
        assert resp.status_code in (200, 500)

    def test_run_with_force_mode_tool(self, client):
        """v0.3 added: force_mode='tool' routes to KeywordRouterAgent."""
        resp = client.post(
            "/agent/run",
            json={"task": "calculate 7 * 6", "force_mode": "tool"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["intent"] == "tool_call"
        assert data["pattern"] == "keyword_router"
        # The v0.1 calculator tool returns "Result: <expr>"
        assert "Result" in data["final_output"]

    def test_run_with_force_mode_model(self, client):
        """v0.3 added: force_mode='model' routes to a cooperation pattern."""
        resp = client.post(
            "/agent/run",
            json={"task": "calculate 7 * 6", "force_mode": "model"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["intent"] == "model_call"
        assert data["pattern"] in ("cascade", "plan_execute_validate", "ensemble")

    def test_run_auto_classifies_tool_query(self, client):
        """v0.3 added: queries with tool keywords auto-route to the tool path."""
        # Calculator: "calculate" is the keyword, and the query has digits
        resp = client.post(
            "/agent/run",
            json={"task": "calculate 99 + 1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["intent"] == "tool_call"
        assert data["pattern"] == "keyword_router"
        assert "Result" in data["final_output"]

    def test_run_auto_classifies_model_query(self, client):
        """v0.3 added: queries without tool keywords go to the model path."""
        resp = client.post(
            "/agent/run",
            json={"task": "What is the meaning of life?"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["intent"] == "model_call"
        # Pattern should be the default (cascade) since none was specified
        assert data["pattern"] == "cascade"

    def test_run_rejects_invalid_force_mode(self, client):
        """force_mode must be 'tool' or 'model'."""
        resp = client.post(
            "/agent/run",
            json={"task": "test", "force_mode": "invalid"},
        )
        assert resp.status_code == 422  # Pydantic validation


# ---- v0.3 integration tests -------------------------------------------------

class TestAriaAgentV3Integration:
    """Tests for the v0.3 orchestrator that unifies v0.1 + v0.2.

    Reuses FakeProvider / FakeRegistry from test_cooperation (duck-typed —
    anything with `get(name)` and `list_providers()` works).
    """

    @pytest.fixture
    def registry(self):
        good_response = "This is a perfectly fine model answer with enough detail."
        return FakeRegistry({
            "opencode-go": FakeProvider("opencode-go", [good_response]),
            "minimax-direct": FakeProvider("minimax-direct", [good_response]),
        })

    @pytest.fixture
    def router(self):
        from aria_agent.router import ModelSelector, get_default_routing_table
        return ModelSelector(get_default_routing_table())

    @pytest.fixture
    def tool_registry(self):
        from aria_agent.tools import ToolRegistry
        from aria_agent.builtin_tools.calculator import CalculatorInput, calculator
        from aria_agent.builtin_tools.web_search import WebSearchInput, web_search

        reg = ToolRegistry()
        reg.register("calculator", CalculatorInput)(calculator)
        reg.register("web_search", WebSearchInput)(web_search)
        return reg

    def test_agent_built_without_tool_registry(self, registry, router):
        """v0.3: tool_registry is optional. Without it, every query goes to the model path."""
        from aria_agent.agent import AriaAgent
        agent = AriaAgent(registry=registry, router=router)
        assert agent.tool_registry is None
        assert agent.legacy_agent is None
        assert agent.approval_gate is None

    def test_agent_built_with_tool_registry(self, registry, router, tool_registry):
        """v0.3: tool_registry + auto-built approval gate + auto-built legacy agent."""
        from aria_agent.agent import AriaAgent
        agent = AriaAgent(registry=registry, router=router, tool_registry=tool_registry)
        assert agent.tool_registry is tool_registry
        assert agent.legacy_agent is not None
        assert agent.approval_gate is not None  # auto-built

    def test_classify_intent_tool_query(self, registry, router, tool_registry):
        from aria_agent.agent import AriaAgent, Intent
        agent = AriaAgent(registry=registry, router=router, tool_registry=tool_registry)
        c = agent.classify_intent("calculate 5 + 3")
        assert c.intent == Intent.TOOL_CALL
        assert c.matched_tool == "calculator"
        assert c.matched_keyword == "calculate"

    def test_classify_intent_model_query(self, registry, router, tool_registry):
        from aria_agent.agent import AriaAgent, Intent
        agent = AriaAgent(registry=registry, router=router, tool_registry=tool_registry)
        c = agent.classify_intent("What is the meaning of life?")
        assert c.intent == Intent.MODEL_CALL
        assert c.matched_tool is None

    def test_classify_intent_no_tool_registry(self, registry, router):
        """No tool registry → everything goes to the model path."""
        from aria_agent.agent import AriaAgent, Intent
        agent = AriaAgent(registry=registry, router=router)
        c = agent.classify_intent("calculate 2 + 2")  # Even with the keyword
        assert c.intent == Intent.MODEL_CALL

    def test_classify_intent_calculate_no_digits(self, registry, router, tool_registry):
        """'calculate' without a numeric expression → model path (explanation)."""
        from aria_agent.agent import AriaAgent, Intent
        agent = AriaAgent(registry=registry, router=router, tool_registry=tool_registry)
        c = agent.classify_intent("calculate the impact of AI on jobs")
        assert c.intent == Intent.MODEL_CALL

    def test_run_tool_path_uses_keyword_router(self, registry, router, tool_registry):
        """Forcing tool mode should call the v0.1 KeywordRouterAgent and wrap the result."""
        from aria_agent.agent import AriaAgent
        agent = AriaAgent(registry=registry, router=router, tool_registry=tool_registry)
        result = asyncio.run(agent.run("calculate 5 + 3", force_mode="tool"))
        assert result.pattern == "keyword_router"
        assert result.metadata["intent"] == "tool_call"
        # v0.1 calculator tool returns "Result: 5 + 3"
        assert "Result" in result.final_output
        # Should have exactly 1 step (the tool call)
        assert result.num_steps == 1

    def test_run_model_path_uses_cooperation(self, registry, router, tool_registry):
        """Forcing model mode should call the cooperation pattern."""
        from aria_agent.agent import AriaAgent
        agent = AriaAgent(registry=registry, router=router, tool_registry=tool_registry)
        result = asyncio.run(agent.run("calculate 5 + 3", force_mode="model"))
        # cascade is the default pattern; pattern field shows the cooperation pattern
        assert result.pattern in ("cascade", "plan_execute_validate", "ensemble")
        assert result.metadata["intent"] == "model_call"

    def test_run_auto_dispatch(self, registry, router, tool_registry):
        """Without force_mode, intent classification decides the path."""
        from aria_agent.agent import AriaAgent
        agent = AriaAgent(registry=registry, router=router, tool_registry=tool_registry)
        # Tool keyword + digits → tool path
        r1 = asyncio.run(agent.run("calculate 5 + 3"))
        assert r1.metadata["intent"] == "tool_call"
        # No tool keyword → model path
        r2 = asyncio.run(agent.run("What is the meaning of life?"))
        assert r2.metadata["intent"] == "model_call"

    def test_tool_path_metadata_includes_v0_1_trace(self, registry, router, tool_registry):
        """The tool-path result's metadata should include the v0.1 trace + cost info."""
        from aria_agent.agent import AriaAgent
        agent = AriaAgent(registry=registry, router=router, tool_registry=tool_registry)
        result = asyncio.run(agent.run("calculate 5 + 3", force_mode="tool"))
        # v0.1 components are wrapped into metadata
        assert "v0_1_trace" in result.metadata
        assert "v0_1_cost" in result.metadata
        assert "classification_reason" in result.metadata
