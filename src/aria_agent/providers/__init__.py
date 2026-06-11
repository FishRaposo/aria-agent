"""Provider layer for Aria Agent.

Each provider wraps a single LLM routing endpoint (a base URL + auth shape).
Models live across providers — the router picks a (provider, model) pair.

Currently supported:
- MiniMax direct (OpenAI-compatible, custom base URL)
- OpenCode Go (OCG, mixed protocol — chat-completions + Anthropic SDK)
- OpenAI Codex (OAuth-only, OpenAI-compatible)
- Command Code (CLI subprocess wrapper — separate from HTTP providers)

Each provider exposes:
- name: short identifier (e.g. "opencode-go")
- chat(): unified async chat-completion call returning LLMResponse
- get_models(): list of model IDs this provider serves
- health_check(): probe the provider is reachable
"""
from .base import BaseProvider, ProviderError
from .minimax import MiniMaxProvider
from .opencode_go import OpenCodeGoProvider
from .openai_codex import OpenAICodexProvider
from .registry import ProviderRegistry, get_default_registry

__all__ = [
    "BaseProvider",
    "ProviderError",
    "MiniMaxProvider",
    "OpenCodeGoProvider",
    "OpenAICodexProvider",
    "ProviderRegistry",
    "get_default_registry",
]
