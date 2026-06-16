"""Agent loop tests — sim routing, permissions, approval pausing, tracing."""

from hermes.agents import HermesAgent, RunResult
from hermes.approvals import ApprovalGate
from hermes.memory import AgentMemory
from hermes.routing import build_router
from hermes.store import InMemoryApprovalStore
from hermes.tools import build_default_registry


class TestAgentRun:
    def test_calculator_flow_returns_result(self, sim_llm_agent):
        result = sim_llm_agent.run_structured("calculate 120 + 350")
        assert result.status == "completed"
        assert "470" in result.response

    def test_run_string_backcompat(self, keyword_agent):
        out = keyword_agent.run("calculate 2 + 2")
        assert isinstance(out, str)
        assert "4" in out

    def test_no_tool_match_generates_response(self, sim_llm_agent):
        result = sim_llm_agent.run_structured("hello there friend")
        assert result.status == "completed"
        assert isinstance(result.response, str) and result.response

    def test_empty_query(self, keyword_agent):
        result = keyword_agent.run_structured("")
        assert isinstance(result, RunResult)

    def test_memory_records_user_and_system(self, keyword_agent):
        keyword_agent.run_structured("calculate 1 + 1")
        roles = [m["role"] for m in keyword_agent.memory.get_context()]
        assert "user" in roles
        assert "system" in roles

    def test_trace_has_spans(self, keyword_agent):
        result = keyword_agent.run_structured("calculate 3 + 4")
        spans = result.trace["spans"]
        # Root run span + decision span + tool span.
        assert len(spans) >= 3
        names = [s["name"] for s in spans]
        assert "agent.run" in names
        assert any(n.startswith("tool.") for n in names)

    def test_trace_id_is_propagated(self, keyword_agent):
        result = keyword_agent.run_structured("calculate 1 + 2")
        trace_id = result.trace["trace_id"]
        assert all(s["trace_id"] == trace_id for s in result.trace["spans"])

    def test_cost_tracked_for_llm_routing(self, sim_llm_agent):
        result = sim_llm_agent.run_structured("search for python")
        assert result.cost["total_calls"] >= 1
        assert result.cost["total_cost"] >= 0.0


class TestApprovalGating:
    def _gated_agent(self, store):
        registry = build_default_registry()
        return HermesAgent(
            registry,
            ApprovalGate(enabled=True, mode="approval_gated", store=store),
            router=build_router("keyword"),
            memory=AgentMemory(),
            mode="approval_gated",
        )

    def test_risky_tool_pauses_for_approval(self):
        store = InMemoryApprovalStore()
        agent = self._gated_agent(store)
        result = agent.run_structured("create a task to do the thing")
        assert result.status == "pending_approval"
        assert result.approval is not None
        assert result.approval["status"] == "pending"

    def test_safe_tool_runs_in_gated_mode(self):
        store = InMemoryApprovalStore()
        agent = self._gated_agent(store)
        result = agent.run_structured("calculate 5 + 5")
        assert result.status == "completed"
        assert "10" in result.response

    def test_free_running_executes_risky_tool(self, keyword_agent):
        result = keyword_agent.run_structured("create a task to do the thing")
        assert result.status == "completed"
        assert "Task created" in result.response

    def test_execute_approved_runs_tool(self):
        store = InMemoryApprovalStore()
        agent = self._gated_agent(store)
        pending = agent.run_structured("create a task to file taxes")
        store.decide(pending.approval["id"], approved=True)
        decided = store.get(pending.approval["id"])
        out = agent.execute_approved(decided["action"], decided["parameters"])
        assert "Task created" in out


class TestToolErrors:
    def test_unknown_tool_returns_error(self, registry):
        from hermes.routing import RouteDecision
        from hermes.tracing import TraceLog

        agent = HermesAgent(
            registry,
            ApprovalGate(enabled=True, mode="free_running"),
            router=build_router("keyword"),
            memory=AgentMemory(),
        )
        # Drive _execute_tool directly with an unknown tool.
        resp, status = agent._execute_tool(
            RouteDecision(tool="ghost", arguments={}), TraceLog()
        )
        assert status == "error"
        assert "not available" in resp
