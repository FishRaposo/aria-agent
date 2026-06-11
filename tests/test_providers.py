"""Tests for the provider layer.

These tests focus on the wiring (model lists, registry, resolve_model) rather
than live API calls. Live-call tests would need real API keys; we mock the
SDKs so the unit tests run offline.
"""
import os
import sys
from unittest.mock import patch

import pytest


# Path setup so tests can import aria_agent without installing it.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "operator-shared-core", "src"))


class TestProviderModelLists:
    """Verify the static model catalogs each provider claims to serve."""

    def test_minimax_lists_M3_as_default(self):
        from aria_agent.providers.minimax import MiniMaxProvider

        models = MiniMaxProvider().get_models()
        assert "MiniMax-M3" in models, "M3 is the default session model"

    def test_minimax_lists_legacy_models(self):
        from aria_agent.providers.minimax import MiniMaxProvider

        models = MiniMaxProvider().get_models()
        # Legacy kept for fallback per the catalog.
        for m in ("MiniMax-M2.7", "MiniMax-M2.5"):
            assert m in models, f"{m} should be in MiniMax direct catalog"

    def test_ocg_includes_chat_completions_models(self):
        from aria_agent.providers.opencode_go import (
            OCG_CHAT_COMPLETIONS_MODELS,
            OpenCodeGoProvider,
        )

        models = OpenCodeGoProvider().get_models()
        for m in ("kimi-k2.6", "kimi-k2.5", "minimax-m2.7", "mimo-v2.5"):
            assert m in models, f"{m} should be in OCG chat-completions catalog"
            assert m in OCG_CHAT_COMPLETIONS_MODELS

    def test_ocg_anthropic_path_is_empty_on_go_plan(self):
        """On the user's Go plan, the Anthropic-SDK path in OCG is empty.

        qwen-3.7-max is in OCG's wider catalog but returns
        "Model X is not supported" on this plan. The Codex chat-completions
        endpoint also doesn't accept it. So OCG_ANTHROPIC_MESSAGES_MODELS
        should be empty — anything in it would be a phantom model that
        breaks the cascade.
        """
        from aria_agent.providers.opencode_go import (
            OCG_ANTHROPIC_MESSAGES_MODELS,
            OpenCodeGoProvider,
        )

        # On the Go plan: no Anthropic-path models are callable
        assert OCG_ANTHROPIC_MESSAGES_MODELS == [], (
            "OCG's Anthropic SDK path is empty on the Go plan — qwen-3.7-max "
            "and friends are in the catalog but not callable. If you add a "
            "model here, verify it's actually live on this plan first."
        )
        # qwen-3.7-max still appears in the overall model list (as a Pro+
        # catalog entry), but the provider's get_models() should NOT claim
        # to serve it.
        all_ocg_models = OpenCodeGoProvider().get_models()
        assert "qwen-3.7-max" not in all_ocg_models, (
            "qwen-3.7-max MUST NOT be in OCG's get_models() on this plan — "
            "it's a phantom model that would break SubAgent picks."
        )

    def test_codex_lists_gpt_5_5_and_gpt_5_4_mini(self):
        from aria_agent.providers.openai_codex import OpenAICodexProvider

        models = OpenAICodexProvider().get_models()
        # Active Codex pool: gpt-5.5 (frontier) + gpt-5.4-mini (M3 chain 2nd fallback).
        # gpt-5.4-mini is the documented fallback in the M3 chain
        # (see aria_agent/router/routing_table.py — MiniMax-M3's fallback_chain).
        # Live verification is blocked on a missing OPENAI_CODEX_OAUTH_TOKEN.
        assert "gpt-5.5" in models
        assert "gpt-5.4-mini" in models


class TestRegistry:
    """Verify the registry routes model IDs to the right providers."""

    def test_registry_constructs_without_keys(self):
        """Registry should not raise even if no API keys are set."""
        from aria_agent.providers.registry import ProviderRegistry

        # Clear all known keys
        with patch.dict(os.environ, {}, clear=True):
            reg = ProviderRegistry()
        assert isinstance(reg.list_providers(), list)

    def test_registry_registers_ocg_when_key_set(self):
        from aria_agent.providers.registry import ProviderRegistry

        with patch.dict(os.environ, {"OPENCODE_GO_API_KEY": "fake-key"}):
            reg = ProviderRegistry()
        assert "opencode-go" in reg.list_providers()

    def test_resolve_model_finds_ocg_for_kimi(self):
        from aria_agent.providers.registry import ProviderRegistry

        with patch.dict(os.environ, {"OPENCODE_GO_API_KEY": "fake-key"}):
            reg = ProviderRegistry()
        provider_name, provider = reg.resolve_model("kimi-k2.6")
        assert provider_name == "opencode-go"
        assert "kimi-k2.6" in provider.get_models()

    def test_resolve_model_finds_minimax_for_M3(self):
        from aria_agent.providers.registry import ProviderRegistry

        with patch.dict(
            os.environ,
            {"OPENCODE_GO_API_KEY": "fake-key", "MINIMAX_API_KEY": "fake-key"},
        ):
            reg = ProviderRegistry()
        provider_name, provider = reg.resolve_model("MiniMax-M3")
        assert provider_name == "minimax-direct"
        assert "MiniMax-M3" in provider.get_models()

    def test_resolve_model_raises_for_unknown(self):
        from aria_agent.providers.registry import ProviderRegistry

        with patch.dict(os.environ, {"OPENCODE_GO_API_KEY": "fake-key"}):
            reg = ProviderRegistry()
        with pytest.raises(KeyError) as exc_info:
            reg.resolve_model("this-model-does-not-exist")
        assert "this-model-does-not-exist" in str(exc_info.value)

    def test_all_models_returns_provider_breakdown(self):
        from aria_agent.providers.registry import ProviderRegistry

        with patch.dict(
            os.environ,
            {"OPENCODE_GO_API_KEY": "fake-key", "MINIMAX_API_KEY": "fake-key"},
        ):
            reg = ProviderRegistry()
        all_models = reg.all_models()
        assert "opencode-go" in all_models
        assert "minimax-direct" in all_models
        assert isinstance(all_models["opencode-go"], list)
        assert "kimi-k2.6" in all_models["opencode-go"]
        assert "MiniMax-M3" in all_models["minimax-direct"]


class TestM3FallbackChain:
    """The M3 default flow: minimax-direct/MiniMax-M3 → opencode-go/minimax-m3
    → openai-codex/gpt-5.4-mini. Documented in the routing table on
    MiniMax-M3's entry.

    These tests exercise the chain under three provider configurations:
    - All providers registered (the M3 wins via minimax-direct)
    - Only OCG registered (M3 chain falls through to opencode-go/minimax-m3)
    - Only Codex registered (M3 chain falls through to openai-codex/gpt-5.4-mini)
    """

    def _make_decision(self):
        """Build a RoutingDecision with MiniMax-M3 as primary."""
        from aria_agent.router import RoutingDecision, TaskType
        from aria_agent.router.routing_table import get_default_routing_table
        table = get_default_routing_table()
        m3 = next(m for m in table.all() if m.model_id == "MiniMax-M3")
        return RoutingDecision(primary=m3, task_type=TaskType.GENERAL)

    def test_chain_uses_minimax_direct_when_registered(self):
        """When MiniMax direct is registered, the chain stops at step 1."""
        from aria_agent.providers.registry import ProviderRegistry

        with patch.dict(
            os.environ,
            {"MINIMAX_API_KEY": "fake-key", "OPENCODE_GO_API_KEY": "fake-key"},
        ):
            reg = ProviderRegistry()
        decision = self._make_decision()
        provider_name, model_id = reg.resolve_decision(decision)
        assert provider_name == "minimax-direct"
        assert model_id == "MiniMax-M3"

    def test_chain_falls_back_to_ocg_when_minimax_direct_unavailable(self):
        """When only OCG is registered, the chain falls to step 2
        (opencode-go/minimax-m3 — the OCG mirror, verified live 2026-06-10)."""
        from aria_agent.providers.registry import ProviderRegistry

        with patch.dict(
            os.environ,
            {"OPENCODE_GO_API_KEY": "fake-key"},
            clear=False,
        ):
            # Remove minimax-direct key if present
            env_no_minimax = {k: v for k, v in os.environ.items() if k != "MINIMAX_API_KEY"}
            with patch.dict(os.environ, env_no_minimax, clear=True):
                reg = ProviderRegistry()
        decision = self._make_decision()
        provider_name, model_id = reg.resolve_decision(decision)
        assert provider_name == "opencode-go"
        assert model_id == "minimax-m3", (
            "M3 chain step 2 should pick the OCG mirror of M3, not minimax-m2.7. "
            "The two are different models on the wire — M3 is minimax-m3, "
            "M2.7 is minimax-m2.7."
        )

    def test_chain_falls_back_to_codex_when_only_codex_registered(self):
        """When only Codex is registered, the chain falls to step 3
        (openai-codex/gpt-5.4-mini — the M3 chain's 2nd fallback)."""
        from aria_agent.providers.registry import ProviderRegistry

        with patch.dict(os.environ, {"OPENAI_CODEX_OAUTH_TOKEN": "fake-token"}, clear=True):
            reg = ProviderRegistry()
        decision = self._make_decision()
        provider_name, model_id = reg.resolve_decision(decision)
        assert provider_name == "openai-codex"
        assert model_id == "gpt-5.4-mini"

    def test_chain_walks_in_documented_order(self):
        """The chain order is M3 → OCG/M3 → Codex/mini. Verify by setting
        up the registry with only Codex and confirming gpt-5.4-mini wins
        (last step in the chain)."""
        from aria_agent.providers.registry import ProviderRegistry

        # With all 3 providers registered, the chain stops at minimax-direct.
        # With only Codex, the chain walks all 3 steps before reaching the
        # Codex provider.
        with patch.dict(os.environ, {"OPENAI_CODEX_OAUTH_TOKEN": "fake-token"}, clear=True):
            reg = ProviderRegistry()
        decision = self._make_decision()
        # Step 1: minimax-direct / MiniMax-M3 — not registered
        # Step 2: opencode-go / minimax-m3 — not registered
        # Step 3: openai-codex / gpt-5.4-mini — registered, wins
        provider_name, model_id = reg.resolve_decision(decision)
        assert (provider_name, model_id) == ("openai-codex", "gpt-5.4-mini")

    def test_minimax_m3_and_MiniMax_M3_are_distinct_model_ids(self):
        """The chain works because minimax-m3 (OCG, lowercase-hyphen) and
        MiniMax-M3 (MiniMax direct, upper-mixed-case) are DIFFERENT model
        IDs on the wire. They're not aliases — the providers serve them
        independently. The OCG provider was missing minimax-m3 from its
        known models list (verified gap 2026-06-10); the registry needs
        both IDs to walk the chain correctly."""
        from aria_agent.providers.opencode_go import OpenCodeGoProvider

        ocg_models = OpenCodeGoProvider().get_models()
        assert "minimax-m3" in ocg_models  # OCG mirror
        assert "MiniMax-M3" not in ocg_models  # MiniMax direct naming, not on OCG

        from aria_agent.providers.minimax import MiniMaxProvider
        mm_models = MiniMaxProvider().get_models()
        assert "MiniMax-M3" in mm_models  # MiniMax direct naming
        assert "minimax-m3" not in mm_models  # OCG naming, not on MiniMax direct


class TestProviderErrors:
    """Verify error handling when API keys are missing or calls fail."""

    def test_provider_raises_on_missing_key_for_chat(self):
        from aria_agent.providers.minimax import MiniMaxProvider
        from aria_agent.providers.base import ProviderError

        with patch.dict(os.environ, {}, clear=True):
            provider = MiniMaxProvider()
            with pytest.raises(ProviderError) as exc_info:
                # No key in env, no explicit key — must raise
                provider._get_client()
        assert "minimax-direct" in str(exc_info.value)

    def test_health_check_returns_false_on_missing_key(self):
        """health_check should not raise — it returns False on auth failure."""
        from aria_agent.providers.minimax import MiniMaxProvider

        with patch.dict(os.environ, {}, clear=True):
            provider = MiniMaxProvider()
            # Should return False, not raise
            import asyncio
            result = asyncio.run(provider.health_check())
        assert result is False
