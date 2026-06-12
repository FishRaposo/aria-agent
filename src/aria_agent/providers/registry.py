"""Provider registry — central catalog of (provider, model) pairs.

The router queries this registry to answer: "For a given model ID, which
provider serves it?" and "What models does provider X serve?"

Single source of truth: the routing table (in `aria_agent.router.routing_table`)
references models by ID, and the registry resolves those IDs to live provider
instances.
"""
import os
from typing import Iterator, Optional

from .base import BaseProvider
from .minimax import MiniMaxProvider
from .openai_codex import OpenAICodexProvider
from .opencode_go import OpenCodeGoProvider
from .zen import ZenProvider


class ProviderRegistry:
    """Holds all configured providers and routes model IDs to them.

    The registry is constructed once at app startup and shared across requests.
    Providers are constructed lazily on first use (so missing API keys don't
    block startup — they're caught when the provider is actually called).
    """

    def __init__(self):
        # Ordered by preference: OCG first (most models, user's primary open route),
        # then MiniMax direct, then Codex (OAuth-only). The router may pick any
        # of them; this list is the "which provider serves this model" map.
        self._providers: dict[str, BaseProvider] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        """Register all default providers, but only if their keys are configured.

        A provider is constructed eagerly if its env var is set; otherwise it's
        constructed on first use (so a missing key surfaces at call time, not
        import time).
        """
        # OpenCode Go — the user's primary open-weights route.
        # (/zen/go/v1/, free Go tier, open source models only.)
        if os.environ.get("OPENCODE_GO_API_KEY"):
            self._providers["opencode-go"] = OpenCodeGoProvider()

        # Zen — the same key, the closed-source tier (/zen/v1/, paid Pro).
        # Most calls on a $1/mo Go plan return 401 "Insufficient balance";
        # the routing table's fallback_chain walks to a callable alternative.
        if os.environ.get("OPENCODE_GO_API_KEY"):
            self._providers["zen"] = ZenProvider()

        # MiniMax direct — the user's default operating model.
        # Accept the canonical uppercase env var and the historical mixed-case
        # typo for backward compatibility.
        if os.environ.get("MINIMAX_API_KEY") or os.environ.get("MiniMax_API_KEY"):
            self._providers["minimax-direct"] = MiniMaxProvider()

        # OpenAI Codex — OAuth-only, frontier escalation target.
        if os.environ.get("OPENAI_CODEX_OAUTH_TOKEN"):
            self._providers["openai-codex"] = OpenAICodexProvider()

    def register(self, provider: BaseProvider) -> None:
        """Add or replace a provider in the registry."""
        self._providers[provider.name] = provider

    def get(self, name: str) -> BaseProvider:
        """Look up a provider by name. Raises KeyError if not registered."""
        if name not in self._providers:
            raise KeyError(
                f"Provider '{name}' not registered. "
                f"Available: {sorted(self._providers.keys())}"
            )
        return self._providers[name]

    def list_providers(self) -> list[str]:
        return sorted(self._providers.keys())

    def resolve_model(self, model_id: str) -> tuple[str, BaseProvider]:
        """Find the (provider_name, provider) that serves a given model ID.

        Iterates registered providers and asks each one if it serves this model.
        The first match wins. If multiple providers serve the same model ID
        (e.g. MiniMax-M3 on both MiniMax direct and OCG), the one registered
        first wins.

        Raises:
            KeyError: if no provider serves the requested model.
        """
        for name, provider in self._providers.items():
            if model_id in provider.get_models():
                return name, provider
        raise KeyError(
            f"No registered provider serves model '{model_id}'. "
            f"Registered providers: {sorted(self._providers.keys())}. "
            f"Check your API keys or update the provider catalog."
        )

    def has_model(self, model_id: str) -> bool:
        """Return True iff at least one registered provider serves `model_id`.

        This is the non-raising variant of `resolve_model`. Useful for selectors
        and orchestrators that want to filter candidates by what's actually
        available in this environment (vs. what's only in the routing table).
        """
        for provider in self._providers.values():
            if model_id in provider.get_models():
                return True
        return False

    def resolve_decision(self, decision) -> tuple[str, str]:
        """Resolve a RoutingDecision to (provider_name, model_id), falling back.

        Tries primary → fallback → escalation in order. Returns the first one
        whose model is actually served by a registered provider. This is the
        right entry point for SubAgent / orchestrator code that needs a
        *callable* model — the routing table's "preferred" model may be on a
        provider that isn't registered in the current environment (e.g. on
        Termux with only OPENCODE_GO_API_KEY set, minimax-direct is in the
        routing table but no provider for it is registered).

        For each slot, the registry also walks the slot's `ModelInfo.fallback_chain`
        (a tuple of (provider_name, model_id) pairs) if the slot's own model isn't
        callable. This is the M3 default chain: when MiniMax-M3 (minimax-direct)
        isn't callable, the registry tries opencode-go/minimax-m3 (the OCG mirror)
        next, then openai-codex/gpt-5.4-mini last. The chain is declared on
        ModelInfo so the same walk applies to any model with a configured chain.

        Falls back through the decision's own chain first; if every model in the
        decision is unregistered, tries:
          1. The default model from the routing table (if it has one)
          2. The cheap workhorse (if there is one)
          3. Any model served by any registered provider

        Returns:
            (provider_name, model_id) — the provider is registered and
            serves the model_id.

        Raises:
            KeyError: only if no registered provider serves any model at all
            (i.e. no API keys are set). Empty routing table is OK — the
            decision just won't resolve.
        """
        # Try primary → fallback → escalation. For each, also walk the
        # ModelInfo's explicit fallback_chain (if set) before giving up
        # on that slot.
        for slot_name in ("primary", "fallback", "escalation"):
            slot_model = getattr(decision, slot_name, None)
            if slot_model is None:
                continue
            # First try the slot's own model
            hit = self._try_callable(slot_model.model_id)
            if hit is not None:
                return hit
            # Then walk the slot's explicit provider-level fallback chain
            for chain_provider, chain_model_id in slot_model.fallback_chain:
                hit = self._try_callable_in_provider(chain_provider, chain_model_id)
                if hit is not None:
                    return hit
            # Then the slot's nested chain is exhausted — try the next slot

        # Decision chain exhausted — try the routing table's defaults.
        # Lazy import to avoid a circular import (router imports providers).
        from ..router.routing_table import get_default_routing_table
        table = get_default_routing_table()

        # Try the default model (and its fallback chain, if any)
        try:
            default = table.default_model()
            hit = self._try_callable(default.model_id)
            if hit is not None:
                return hit
            for chain_provider, chain_model_id in default.fallback_chain:
                hit = self._try_callable_in_provider(chain_provider, chain_model_id)
                if hit is not None:
                    return hit
        except (KeyError, IndexError, ValueError):
            pass

        # Try the cheap workhorse
        for m in table.cheap_pool():
            if self.has_model(m.model_id):
                name, _ = self.resolve_model(m.model_id)
                return name, m.model_id

        # Try any registered model
        for name, provider in self._providers.items():
            models = provider.get_models()
            if models:
                return name, models[0]

        # Nothing registered at all
        raise KeyError(
            "No registered providers serve any model. "
            "Set at least one API key (OPENCODE_GO_API_KEY, MiniMax_API_KEY, "
            "OPENAI_CODEX_OAUTH_TOKEN) and try again."
        )

    def _try_callable(self, model_id: str) -> Optional[tuple[str, str]]:
        """Return (provider_name, model_id) if `model_id` is callable, else None."""
        if self.has_model(model_id):
            name, _ = self.resolve_model(model_id)
            return name, model_id
        return None

    def _try_callable_in_provider(
        self, provider_name: str, model_id: str
    ) -> Optional[tuple[str, str]]:
        """Return (provider_name, model_id) if this specific provider is registered
        AND serves `model_id`, else None. Used to walk ModelInfo.fallback_chain."""
        try:
            provider = self.get(provider_name)
        except KeyError:
            return None
        if model_id in provider.get_models():
            return provider_name, model_id
        return None

    def all_models(self) -> dict[str, list[str]]:
        """Return a mapping of provider_name → model_ids for the API surface."""
        return {name: p.get_models() for name, p in self._providers.items()}

    def __iter__(self) -> Iterator[BaseProvider]:
        return iter(self._providers.values())


_default_registry: Optional[ProviderRegistry] = None


def get_default_registry() -> ProviderRegistry:
    """Return the process-wide default registry (constructed on first call)."""
    global _default_registry
    if _default_registry is None:
        _default_registry = ProviderRegistry()
    return _default_registry


def reset_default_registry() -> None:
    """Reset the process-wide registry (for testing)."""
    global _default_registry
    _default_registry = None
