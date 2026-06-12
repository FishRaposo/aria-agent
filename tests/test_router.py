"""Tests for the router layer (routing table, classifier, selector)."""
import os
import sys

import pytest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "operator-shared-core", "src"))


class TestRoutingTable:
    def test_active_pool_has_15_models(self):
        from aria_agent.router import get_default_routing_table

        table = get_default_routing_table()
        # Active = 8 (M3, k2.6, k2.5, minimax-m3, m2.7, m2.5, mimo-v2.5,
        # mimo-v2.5-pro) + 6 Pro+ (qwen-3.7-max, qwen-3.7-plus, qwen-3.6-max,
        # qwen-3.6-plus, nemotron-3-ultra, gpt-5.5, gpt-5.4-mini) = 15 total
        # Active = 8, Pro+ = 7
        assert len(table.all()) == 15
        assert len(table.active_pool()) == 8

    def test_default_model_is_M3(self):
        from aria_agent.router import get_default_routing_table

        table = get_default_routing_table()
        default = table.default_model()
        assert default.model_id == "MiniMax-M3"
        assert default.provider_name == "minimax-direct"
        # The default model has the explicit M3 chain: Zen mirror → Codex mini
        # (2026-06-11: M3 closed source moved from opencode-go to zen)
        assert ("zen", "minimax-m3") in default.fallback_chain
        assert ("openai-codex", "gpt-5.4-mini") in default.fallback_chain

    def test_find_by_task_returns_active_first(self):
        from aria_agent.router import get_default_routing_table, TaskType

        table = get_default_routing_table()
        # REASONING: has both active (M3, Kimi, GLM, deepseek) and pro+ (gpt-5.5)
        candidates = table.find_by_task(TaskType.REASONING)
        # First should be the active specialist (Kimi, BEST_QUALITY tier)
        assert candidates[0].model_id == "kimi-k2.6"
        # All Pro+ should come last
        pro_plus = [c for c in candidates if c.tier.value == "pro_plus"]
        if pro_plus:
            assert pro_plus == candidates[-len(pro_plus):], (
                "Pro+ candidates should be sorted to the end of the list"
            )

    def test_find_by_task_coding_default_picks_M3(self):
        from aria_agent.router import get_default_routing_table, TaskType

        table = get_default_routing_table()
        # CODING_DEFAULT: only M3 claims it (default model for general coding)
        candidates = table.find_by_task(TaskType.CODING_DEFAULT)
        assert candidates[0].model_id == "MiniMax-M3"

    def test_cheap_pool_returns_only_workhorse(self):
        from aria_agent.router import get_default_routing_table

        table = get_default_routing_table()
        cheap = table.cheap_pool()
        assert all(m.tier.value == "cheap_workhorse" for m in cheap)
        # mimo-v2.5 is the canonical cheap workhorse
        assert any(m.model_id == "mimo-v2.5" for m in cheap)

    def test_find_by_model_id_works(self):
        from aria_agent.router import get_default_routing_table

        table = get_default_routing_table()
        matches = table.find_by_model_id("kimi-k2.6")
        assert len(matches) == 1
        assert matches[0].provider_name == "opencode-go"
        assert matches[0].tier.value == "best_quality"


class TestTaskClassifier:
    @pytest.fixture
    def classifier(self):
        from aria_agent.router import TaskClassifier
        return TaskClassifier()

    def test_classify_vision_keyword(self, classifier):
        from aria_agent.router import TaskType
        assert classifier.classify("Generate an image of a cat") == TaskType.VISION

    def test_classify_code_review(self, classifier):
        from aria_agent.router import TaskType
        assert classifier.classify("Please review this code") == TaskType.CODE_REVIEW

    def test_classify_coding_default_for_function(self, classifier):
        from aria_agent.router import TaskType
        # Coding keywords include "function" — should match
        assert classifier.classify("Write a Python function to compute factorial") == TaskType.CODING_DEFAULT

    def test_classify_reasoning_for_proof(self, classifier):
        from aria_agent.router import TaskType
        assert classifier.classify("Prove the Pythagorean theorem") == TaskType.REASONING

    def test_classify_translation(self, classifier):
        from aria_agent.router import TaskType
        assert classifier.classify("Translate this to Portuguese") == TaskType.TRANSLATION

    def test_classify_escalation_via_explicit_signal(self, classifier):
        from aria_agent.router import TaskType
        assert classifier.classify("Use the best model for this") == TaskType.ESCALATION

    def test_classify_cron(self, classifier):
        from aria_agent.router import TaskType
        assert classifier.classify("cron job every 5 minutes") == TaskType.CRON_BUDGET

    def test_classify_empty_returns_general(self, classifier):
        from aria_agent.router import TaskType
        assert classifier.classify("") == TaskType.GENERAL
        assert classifier.classify("   ") == TaskType.GENERAL

    def test_classify_unknown_returns_general(self, classifier):
        from aria_agent.router import TaskType
        assert classifier.classify("What is the meaning of life?") == TaskType.GENERAL

    def test_classify_long_task_suggests_long_context(self, classifier):
        from aria_agent.router import TaskType
        long_task = "x" * 5000  # No keywords, but very long
        assert classifier.classify(long_task) == TaskType.LONG_CONTEXT


class TestModelSelector:
    @pytest.fixture
    def selector(self):
        from aria_agent.router import ModelSelector, get_default_routing_table
        return ModelSelector(get_default_routing_table())

    def test_select_for_coding_default_picks_M3(self, selector):
        from aria_agent.router import TaskType

        decision = selector.select(TaskType.CODING_DEFAULT)
        assert decision.primary.model_id == "MiniMax-M3"
        assert decision.primary.tier.value == "default"

    def test_select_for_reasoning_picks_kimi(self, selector):
        from aria_agent.router import TaskType

        decision = selector.select(TaskType.REASONING)
        # Best TB on Go plan
        assert decision.primary.model_id == "kimi-k2.6"

    def test_select_for_long_context_picks_kimi_k25(self, selector):
        from aria_agent.router import TaskType

        decision = selector.select(TaskType.LONG_CONTEXT)
        # kimi-k2.5 (MULTIMODAL, 262K context) wins over minimax-m2.7 (DEFAULT,
        # 1M context) for LONG_CONTEXT because tier ordering puts
        # MULTIMODAL < DEFAULT. Even though m2.7 has more raw context, the
        # selector prefers the higher-quality tier for this task.
        # The m2.7 entry also has LONG_CONTEXT in its task_types (it's a
        # natural fit with 1M context) — but it loses the tier tiebreak.
        assert decision.primary.model_id == "kimi-k2.5"

    def test_select_for_bulk_picks_mimo(self, selector):
        from aria_agent.router import TaskType

        decision = selector.select(TaskType.BULK_TRANSFORM)
        # Cheap workhorse
        assert decision.primary.model_id == "mimo-v2.5"

    def test_select_with_budget_cheap(self, selector):
        from aria_agent.router import TaskType

        decision = selector.select(TaskType.CODING_DEFAULT, budget="cheap")
        # Budget override forces cheap workhorse
        assert decision.primary.model_id == "mimo-v2.5"

    def test_select_with_budget_quality(self, selector):
        from aria_agent.router import TaskType

        decision = selector.select(TaskType.CODING_DEFAULT, budget="quality")
        # Quality forces best_quality or default
        assert decision.primary.tier.value in ("best_quality", "default")

    def test_fallback_always_set(self, selector):
        from aria_agent.router import TaskType

        # For all task types, fallback should be non-None
        for tt in [
            TaskType.CODING_DEFAULT, TaskType.REASONING, TaskType.LONG_CONTEXT,
            TaskType.BULK_TRANSFORM, TaskType.VISION, TaskType.ESCALATION,
        ]:
            decision = selector.select(tt)
            assert decision.fallback is not None, f"No fallback for {tt.value}"
            assert decision.fallback.model_id != decision.primary.model_id, (
                f"Fallback is same as primary for {tt.value}"
            )

    def test_escalation_set_for_tasks_with_pro_plus_options(self, selector):
        from aria_agent.router import TaskType

        decision = selector.select(TaskType.ESCALATION)
        # Escalation should have a higher-quality target
        assert decision.escalation is not None
        # Should be Pro+ gpt-5.5 (highest TB score)
        assert decision.escalation.model_id == "gpt-5.5"

    def test_select_for_task_description_end_to_end(self, selector):
        from aria_agent.router import TaskType

        # "Build a multi-step agent" → CODING_LONG_HORIZON → kimi-k2.6
        decision = selector.select_for_task_description(
            "Build a multi-step autonomous agent"
        )
        assert decision.task_type == TaskType.CODING_LONG_HORIZON
        assert decision.primary.model_id == "kimi-k2.6"
