"""Abstract base class for all LLM providers.

A provider wraps a single routing endpoint (base URL + auth shape + protocol).
Multiple models can be served through one provider (e.g. OCG serves Kimi, MiniMax,
Qwen all through different paths but the same API key).

The contract:
- `name`: short identifier used in routing tables and logs
- `chat()`: unified async call returning `LLMResponse` from shared-core
- `get_models()`: list of model IDs the provider is configured to serve
- `health_check()`: probe the provider is reachable; returns bool
"""
from abc import ABC, abstractmethod
from typing import Optional

from shared_core.llm import LLMResponse


class ProviderError(Exception):
    """Raised when a provider call fails (auth, network, model not found, etc.)."""

    def __init__(self, provider: str, message: str, *, status_code: Optional[int] = None):
        self.provider = provider
        self.message = message
        self.status_code = status_code
        super().__init__(f"[{provider}] {message}")


class BaseProvider(ABC):
    """Abstract base for LLM providers.

    Subclasses must implement `chat`, `get_models`, and `health_check`.
    They may also override `close` if they hold persistent connections.
    """

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    async def chat(
        self,
        model: str,
        messages: list[dict],
        *,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> LLMResponse:
        """Send a chat completion request.

        Args:
            model: Provider-specific model ID (e.g. "kimi-k2.6", "MiniMax-M3")
            messages: List of {"role": ..., "content": ...} dicts
            temperature: Sampling temperature
            max_tokens: Max output tokens
            **kwargs: Provider-specific extras (e.g. reasoning_effort, top_p)

        Returns:
            LLMResponse with text, model, token counts, latency, estimated_cost

        Raises:
            ProviderError: on auth, network, or model-not-found failures
        """

    @abstractmethod
    def get_models(self) -> list[str]:
        """Return the list of model IDs this provider is configured to serve.

        Used by the router to validate model selections and by /models endpoint.
        """

    @abstractmethod
    async def health_check(self) -> bool:
        """Probe the provider is reachable. Returns True if OK, False otherwise.

        Should not raise — health checks must be safe to call frequently.
        """

    async def close(self) -> None:
        """Optional cleanup for persistent connections. Default is no-op."""
        return None
