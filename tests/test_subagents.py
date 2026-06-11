"""Tests for the v0.4 sub-agent system: role routing, SubAgent, Orchestrator.

Uses FakeProvider / FakeRegistry from test_cooperation (duck-typed).
"""
import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "operator-shared-core", "src"))
sys.path.insert(0, os.path.dirname(__file__))

from test_cooperation import FakeProvider, FakeRegistry  # noqa: E402


# ---- Fixtures ---------------------------------------------------------------

@pytest.fixture
def registry():
    """Provider registry with fake providers that respond to all models.

    The fake providers list the real model IDs from the routing table,
    so role routing + model overrides work end-to-end.
    """
    ocg_models = [
        "kimi-k2.6", "kimi-k2.5", "deepseek-v4-pro",
        "glm-5.1", "glm-5", "mimo-v2.5",
    ]
    m3_models = ["MiniMax-M3"]

    class FakeOCG(FakeProvider):
        def get_models(self): return ocg_models

    class FakeM3(FakeProvider):
        def get_models(self): return m3_models

    return FakeRegistry({
        "opencode-go": FakeOCG("opencode-go", [
            f"OCG response #{i}: detailed analysis with enough text to pass quality."
            for i in range(20)
        ]),
        "minimax-direct": FakeM3("minimax-direct", [
            f"M3 response #{i}: well-written code with comments."
            for i in range(20)
        ]),
    })


@pytest.fixture
def router():
    from aria_agent.router import ModelSelector, get_default_routing_table
    return ModelSelector(get_default_routing_table())


@pytest.fixture
def sub_agent_registry(registry, router):
    from aria_agent.subagents import SubAgentRegistry
    return SubAgentRegistry(registry, router)


# ---- Role routing tests ----------------------------------------------------

class TestRoleRouting:
    """Test that the router picks the right model for each role."""

    def test_planner_picks_kimi_k26(self, router):
        """Planner should get kimi-k2.6 (best for deep reasoning)."""
        decision = router.select_for_role("planner")
        assert decision.primary.model_id == "kimi-k2.6"
        assert decision.primary.tier.value == "best_quality"

    def test_architect_picks_kimi_k26(self, router):
        """Architect should also get kimi-k2.6 (broad design thinking)."""
        decision = router.select_for_role("architect")
        assert decision.primary.model_id == "kimi-k2.6"

    def test_implementer_picks_M3(self, router):
        """Implementer should get M3 (default, native coding)."""
        decision = router.select_for_role("implementer")
        assert decision.primary.model_id == "MiniMax-M3"

    def test_debugger_picks_kimi(self, router):
        """Debugger should get kimi-k2.6 (best quality, 262K context, analytical)."""
        decision = router.select_for_role("debugger")
        assert decision.primary.model_id == "kimi-k2.6"

    def test_documenter_picks_kimi(self, router):
        """Documenter should get kimi-k2.6 (best quality, writing)."""
        decision = router.select_for_role("documenter")
        assert decision.primary.model_id == "kimi-k2.6"

    def test_reviewer_picks_kimi(self, router):
        """Reviewer should get kimi-k2.6 (best quality, code review, criticism)."""
        decision = router.select_for_role("reviewer")
        assert decision.primary.model_id == "kimi-k2.6"

    def test_tester_picks_M3(self, router):
        """Tester should get M3 (default, edge-case generation)."""
        decision = router.select_for_role("tester")
        assert decision.primary.model_id == "MiniMax-M3"

    def test_validator_picks_kimi(self, router):
        """Validator should get kimi-k2.6 (best quality, correctness verification)."""
        decision = router.select_for_role("validator")
        assert decision.primary.model_id == "kimi-k2.6"

    def test_researcher_picks_kimi(self, router):
        """Researcher should get kimi-k2.6 (best quality, 262K context, synthesis)."""
        decision = router.select_for_role("researcher")
        assert decision.primary.model_id == "kimi-k2.6"

    def test_budget_cheap_forces_workhorse(self, router):
        """budget='cheap' should force mimo-v2.5 regardless of role."""
        decision = router.select_for_role("planner", budget="cheap")
        assert decision.primary.model_id == "mimo-v2.5"

    def test_budget_quality_picks_highest_tb(self, router):
        """budget='quality' should pick the highest-TB model in the role's candidates."""
        # For planner, kimi-k2.6 is best (54.4% TB)
        decision = router.select_for_role("planner", budget="quality")
        # Should still be kimi-k2.6 (it's the highest-TB option)
        assert decision.primary.model_id in ("kimi-k2.6", "gpt-5.5")
        # If gpt-5.5 is in the active pool, it should win
        if decision.primary.model_id == "gpt-5.5":
            assert decision.primary.tier.value == "pro_plus"

    def test_role_decision_includes_fallback(self, router):
        """Role decisions should include a fallback (second candidate or cheap)."""
        for role in ["planner", "implementer", "debugger"]:
            decision = router.select_for_role(role)
            # Fallback is the second candidate, or the cheap workhorse
            assert decision.fallback is not None, f"No fallback for {role}"


# ---- SubAgent tests --------------------------------------------------------

class TestSubAgent:
    """Test the SubAgent class (single-role worker)."""

    def test_subagent_picks_role_model(self, sub_agent_registry):
        """A planner SubAgent should use kimi-k2.6 by default."""
        from aria_agent.router import SubAgentRole
        planner = sub_agent_registry.get(SubAgentRole.PLANNER)
        provider_name, model_id = planner.pick_model()
        assert model_id == "kimi-k2.6"

    def test_subagent_run_returns_subagent_result(self, sub_agent_registry):
        """sub_agent.run() should return a SubAgentResult with full metadata."""
        from aria_agent.router import SubAgentRole
        planner = sub_agent_registry.get(SubAgentRole.PLANNER)
        result = asyncio.run(planner.run("Plan a /health endpoint"))
        assert result.role == SubAgentRole.PLANNER
        assert result.model_id == "kimi-k2.6"
        assert result.provider_name == "opencode-go"
        assert "OCG response" in result.output_text
        assert result.success
        assert result.cost_usd > 0.0  # FakeProvider returns 0.001
        assert result.latency_ms > 0.0

    def test_subagent_with_model_override(self, registry, router):
        """model_id override should bypass the role's default pick."""
        from aria_agent.router import SubAgentRole
        from aria_agent.subagents import SubAgent
        # Force planner to use M3 (not kimi-k2.6)
        planner = SubAgent(
            role=SubAgentRole.PLANNER,
            registry=registry,
            router=router,
            model_id="MiniMax-M3",
        )
        provider_name, model_id = planner.pick_model()
        assert model_id == "MiniMax-M3"
        assert provider_name == "minimax-direct"
        result = asyncio.run(planner.run("Plan a thing"))
        assert result.model_id == "MiniMax-M3"
        assert result.metadata["picked_via"] == "override"

    def test_subagent_role_specific_system_prompt(self, sub_agent_registry):
        """Each role should have a system prompt that primes it for that work."""
        from aria_agent.router import SubAgentRole
        planner = sub_agent_registry.get(SubAgentRole.PLANNER)
        # Access the spec
        from aria_agent.subagents import DEFAULT_ROLE_SPECS
        planner_spec = DEFAULT_ROLE_SPECS[SubAgentRole.PLANNER]
        assert "planning" in planner_spec.system_prompt.lower()
        debugger_spec = DEFAULT_ROLE_SPECS[SubAgentRole.DEBUGGER]
        assert "debug" in debugger_spec.system_prompt.lower()
        # Each role has a distinct prompt
        assert planner_spec.system_prompt != debugger_spec.system_prompt

    def test_subagent_run_with_context(self, sub_agent_registry):
        """Passing context should prepend it to the sub-agent's input."""
        from aria_agent.router import SubAgentRole
        from aria_agent.subagents import DEFAULT_ROLE_SPECS
        planner = sub_agent_registry.get(SubAgentRole.PLANNER)
        result = asyncio.run(
            planner.run("Build the thing", context="We discussed this earlier.")
        )
        # The context should be in input_messages
        context_msg_found = any(
            "We discussed this earlier." in str(m.get("content", ""))
            for m in result.input_messages
        )
        assert context_msg_found, "Context not found in input messages"

    def test_subagent_handles_provider_error(self, registry, router):
        """Provider errors should be returned as failed SubAgentResults."""
        from aria_agent.router import SubAgentRole
        from aria_agent.subagents import SubAgent
        from aria_agent.providers.base import ProviderError

        class ErrorProvider:
            name = "error-provider"
            async def chat(self, **kwargs):
                raise ProviderError("error-provider", "Boom!", status_code=500)
            def get_models(self): return ["mimo-v2.5"]
            async def health_check(self): return False
            async def close(self): return None

        error_reg = FakeRegistry({"error-provider": ErrorProvider()})
        # Use mimo-v2.5 (which ErrorProvider serves) for the role
        sub = SubAgent(
            role=SubAgentRole.PLANNER,
            registry=error_reg,
            router=router,
            model_id="mimo-v2.5",
        )
        result = asyncio.run(sub.run("test"))
        assert not result.success
        assert "Boom" in result.error


# ---- SubAgentRegistry tests ------------------------------------------------

class TestSubAgentRegistry:
    """Test the SubAgentRegistry (role → SubAgent catalog)."""

    def test_registry_has_all_nine_roles(self, sub_agent_registry):
        from aria_agent.router import SubAgentRole
        roles = sub_agent_registry.list_roles()
        assert len(roles) == 9
        for role in SubAgentRole:
            assert role in roles

    def test_registry_get_lazy_builds(self, sub_agent_registry):
        """First call to get() should build the sub-agent; second returns same instance."""
        from aria_agent.router import SubAgentRole
        agent1 = sub_agent_registry.get(SubAgentRole.PLANNER)
        agent2 = sub_agent_registry.get(SubAgentRole.PLANNER)
        assert agent1 is agent2  # Cached

    def test_registry_register_overrides(self, sub_agent_registry):
        """register() should override the default sub-agent for a role."""
        from aria_agent.router import SubAgentRole
        from aria_agent.subagents import SubAgent
        custom = SubAgent(
            role=SubAgentRole.PLANNER,
            registry=sub_agent_registry._registry,
            router=sub_agent_registry._router,
            model_id="mimo-v2.5",
        )
        sub_agent_registry.register(SubAgentRole.PLANNER, custom)
        result = sub_agent_registry.get(SubAgentRole.PLANNER)
        assert result is custom

    def test_registry_register_spec_invalidates_cache(self, sub_agent_registry):
        """register_spec() should invalidate the cached agent so new spec takes effect."""
        from aria_agent.router import SubAgentRole
        from aria_agent.subagents import SubAgentRoleSpec
        original = sub_agent_registry.get(SubAgentRole.PLANNER)
        # Register a new spec
        new_spec = SubAgentRoleSpec(
            role=SubAgentRole.PLANNER,
            system_prompt="Custom prompt",
            temperature=0.1,
            max_tokens=128,
        )
        sub_agent_registry.register_spec(SubAgentRole.PLANNER, new_spec)
        # Getting again should rebuild with new spec
        new = sub_agent_registry.get(SubAgentRole.PLANNER)
        assert new is not original
        assert new.spec.system_prompt == "Custom prompt"
        assert new.spec.temperature == 0.1


# ---- Orchestrator tests ----------------------------------------------------

class TestOrchestrator:
    """Test the Orchestrator (parallel + sequential sub-agent dispatch)."""

    def test_run_parallel_uses_asyncio_gather(self, sub_agent_registry):
        """Parallel run should use asyncio.gather — total time ~ max, not sum."""
        from aria_agent.router import SubAgentRole
        from aria_agent.subagents import Orchestrator
        orch = Orchestrator(sub_agent_registry)
        result = asyncio.run(orch.run_parallel(
            "Plan a thing",
            [SubAgentRole.PLANNER, SubAgentRole.ARCHITECT, SubAgentRole.DEBUGGER],
        ))
        assert result.mode == "parallel"
        assert result.num_steps == 3
        # Each step ran independently
        assert all(s.result.success for s in result.steps)
        # final_output should contain all 3 sub-agents' outputs
        assert "planner" in result.final_output.lower()
        assert "architect" in result.final_output.lower()
        assert "debugger" in result.final_output.lower()

    def test_run_sequential_chains_with_context(self, sub_agent_registry):
        """Sequential run should pass prior output to each subsequent sub-agent."""
        from aria_agent.router import SubAgentRole
        from aria_agent.subagents import Orchestrator
        orch = Orchestrator(sub_agent_registry)
        result = asyncio.run(orch.run_sequential(
            "Build a thing",
            [SubAgentRole.PLANNER, SubAgentRole.IMPLEMENTER, SubAgentRole.VALIDATOR],
        ))
        assert result.mode == "sequential"
        assert result.num_steps == 3
        # final_output is the last sub-agent's output
        assert result.final_output == result.steps[-1].result.output_text
        # Each step's input_messages should contain prior context
        # (the implementer should see the planner's output, the validator should see both)
        impl_input = result.steps[1].result.input_messages
        val_input = result.steps[2].result.input_messages
        # The implementer's input should include the planner's output
        impl_context = " ".join(str(m.get("content", "")) for m in impl_input)
        assert "OCG response" in impl_context or "M3 response" in impl_context
        # The validator's input should include BOTH prior outputs
        val_context = " ".join(str(m.get("content", "")) for m in val_input)
        assert "OCG response" in val_context or "M3 response" in val_context

    def test_run_sequential_pass_full_output_false(self, sub_agent_registry):
        """pass_full_output=False should only pass the last prior output."""
        from aria_agent.router import SubAgentRole
        from aria_agent.subagents import Orchestrator
        orch = Orchestrator(sub_agent_registry)
        result = asyncio.run(orch.run_sequential(
            "Build a thing",
            [SubAgentRole.PLANNER, SubAgentRole.IMPLEMENTER],
            pass_full_output=False,
        ))
        # With pass_full_output=False, the implementer only sees the planner's
        # last output (which IS the planner's only output in this 2-step case)
        impl_input = result.steps[1].result.input_messages
        # The context should be the planner's output, not the whole prior
        impl_context = " ".join(str(m.get("content", "")) for m in impl_input)
        assert "OCG response" in impl_context or "M3 response" in impl_context

    def test_run_parallel_total_latency_near_max(self, sub_agent_registry):
        """Parallel run's total latency should be near max(individual), not sum."""
        from aria_agent.router import SubAgentRole
        from aria_agent.subagents import Orchestrator
        orch = Orchestrator(sub_agent_registry)
        result = asyncio.run(orch.run_parallel(
            "Plan a thing",
            [SubAgentRole.PLANNER, SubAgentRole.IMPLEMENTER, SubAgentRole.DEBUGGER],
        ))
        # The fake providers return 100ms latency each
        # Parallel total should be ~100ms (max), not ~300ms (sum)
        individual_latencies = [s.result.latency_ms for s in result.steps]
        assert all(l > 0 for l in individual_latencies)
        # Total wall-clock should be at most max + overhead, not sum
        max_lat = max(individual_latencies)
        assert result.total_latency_ms < sum(individual_latencies), (
            f"Parallel total {result.total_latency_ms}ms >= sum {sum(individual_latencies)}ms"
        )
        # Should be at most max + some overhead
        assert result.total_latency_ms < (max_lat * 3 + 50)

    def test_run_sequential_total_latency_near_sum(self, sub_agent_registry):
        """Sequential run's total latency should be near sum(individual).

        Note: the orchestrator's `total_latency_ms` is wall-clock (fast for
        fakes). We sum the per-step `latency_ms` from the model responses
        (which is the meaningful "model thinks it took this long" metric).
        """
        from aria_agent.router import SubAgentRole
        from aria_agent.subagents import Orchestrator
        orch = Orchestrator(sub_agent_registry)
        result = asyncio.run(orch.run_sequential(
            "Build a thing",
            [SubAgentRole.PLANNER, SubAgentRole.IMPLEMENTER],
        ))
        # Fake provider reports 100ms per call. Sequential = 100 + 100 = 200ms.
        per_step_latency_sum = sum(s.result.latency_ms for s in result.steps)
        assert per_step_latency_sum == pytest.approx(200.0, abs=0.1), (
            f"Sum of per-step latency {per_step_latency_sum}ms != ~200ms"
        )

    def test_run_parallel_aggregates_cost(self, sub_agent_registry):
        """Parallel run should aggregate cost across all sub-agents."""
        from aria_agent.router import SubAgentRole
        from aria_agent.subagents import Orchestrator
        orch = Orchestrator(sub_agent_registry)
        result = asyncio.run(orch.run_parallel(
            "Plan a thing",
            [SubAgentRole.PLANNER, SubAgentRole.IMPLEMENTER],
        ))
        individual_costs = [s.result.cost_usd for s in result.steps]
        assert result.total_cost_usd == sum(individual_costs)

    def test_run_empty_roles_raises(self, sub_agent_registry):
        """Empty roles list should raise ValueError."""
        from aria_agent.subagents import Orchestrator
        orch = Orchestrator(sub_agent_registry)
        with pytest.raises(ValueError):
            asyncio.run(orch.run_parallel("task", []))
        with pytest.raises(ValueError):
            asyncio.run(orch.run_sequential("task", []))

    def test_orchestrator_result_metadata(self, sub_agent_registry):
        """Result metadata should include roles, budget, mode info."""
        from aria_agent.router import SubAgentRole
        from aria_agent.subagents import Orchestrator
        orch = Orchestrator(sub_agent_registry)
        result = asyncio.run(orch.run_parallel(
            "Plan a thing",
            [SubAgentRole.PLANNER, SubAgentRole.IMPLEMENTER],
            budget="cheap",
        ))
        assert result.metadata["mode"] == "parallel"
        assert "planner" in result.metadata["roles"]
        assert "implementer" in result.metadata["roles"]
        assert result.metadata["budget"] == "cheap"
        assert "task_preview" in result.metadata


# ---- Integration tests -----------------------------------------------------

class TestSubAgentEndToEnd:
    """End-to-end tests showing the v0.4 sub-agent system solving real problems."""

    def test_plan_then_implement(self, sub_agent_registry):
        """Sequential: planner → implementer. Implementer should see plan."""
        from aria_agent.router import SubAgentRole
        from aria_agent.subagents import Orchestrator
        orch = Orchestrator(sub_agent_registry)
        result = asyncio.run(orch.run_sequential(
            "Add a /health endpoint that returns service status",
            [SubAgentRole.PLANNER, SubAgentRole.IMPLEMENTER],
        ))
        # The implementer's input should include the planner's output
        impl_input = result.steps[1].result.input_messages
        context_str = " ".join(str(m.get("content", "")) for m in impl_input)
        # The planner's actual response should be in the implementer's context
        assert "OCG response" in context_str or "M3 response" in context_str
        # The implementer's output is the final
        assert result.final_output == result.steps[-1].result.output_text

    def test_parallel_perspectives(self, sub_agent_registry):
        """Parallel: planner + architect + implementer all see the same task."""
        from aria_agent.router import SubAgentRole
        from aria_agent.subagents import Orchestrator
        orch = Orchestrator(sub_agent_registry)
        result = asyncio.run(orch.run_parallel(
            "Add caching to the FastAPI app",
            # planner/architect pick kimi-k2.6 (BEST_QUALITY, active on OCG);
            # implementer picks MiniMax-M3 (DEFAULT, minimax-direct).
            # On the user's Go plan with both keys set, these are 2 distinct
            # models — verifying the role-based model picking actually fires.
            [SubAgentRole.PLANNER, SubAgentRole.ARCHITECT, SubAgentRole.IMPLEMENTER],
        ))
        # 3 perspectives, all completed
        assert result.num_steps == 3
        assert result.num_succeeded == 3
        assert result.num_failed == 0
        # Each sub-agent should have a model picked; at least 2 distinct
        # (planner/architect → kimi, implementer → M3).
        models_used = {s.result.model_id for s in result.steps}
        assert len(models_used) >= 2, (
            f"expected at least 2 distinct models (kimi + M3), got {models_used}"
        )
        # The implementer specifically should have picked M3
        impl_step = next(s for s in result.steps if s.role == SubAgentRole.IMPLEMENTER)
        assert impl_step.result.model_id == "MiniMax-M3"
        # final_output should contain all 3 sections
        assert result.final_output.count("===") >= 3
