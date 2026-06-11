"""Base class for OpenAI-compatible providers.

Many providers serve the OpenAI Chat Completions API with their own base URL and
auth: MiniMax direct, OpenCode Go, OpenAI Codex, and others. This class consolidates
the boilerplate (async client construction, retry semantics, error mapping) so each
concrete provider only specifies its base URL and how it authenticates.

Concrete subclasses (e.g. `MiniMaxProvider`) override:
- `base_url`: the provider's chat-completions endpoint
- `_get_api_key()`: how to obtain the auth token
- `get_models()`: which model IDs are served
"""
import time
from abc import abstractmethod
from typing import Any

from shared_core.llm import LLMResponse, estimate_llm_cost

from .base import BaseProvider, ProviderError


class OpenAICompatibleProvider(BaseProvider):
    """Base for any provider speaking the OpenAI Chat Completions API.

    Subclasses must set `base_url` and implement `_get_api_key()`. They may
    override `get_models()` to enumerate the model IDs the provider serves.
    """

    # Subclasses set this to the chat-completions endpoint, e.g.
    # "https://api.minimax.io/v1" or "https://opencode.ai/zen/go/v1"
    base_url: str = ""

    def __init__(self, name: str, *, timeout: float = 60.0):
        super().__init__(name)
        self.timeout = timeout
        self._client: Any = None  # lazy: openai.AsyncOpenAI instance

    def _get_api_key(self) -> str:
        """Subclasses return the bearer token / API key for this provider."""
        raise NotImplementedError

    def _get_client(self) -> Any:
        """Lazy-construct the async OpenAI client with the provider's base URL."""
        if self._client is None:
            try:
                import openai  # type: ignore
            except ImportError as e:
                raise ProviderError(
                    self.name,
                    "openai SDK not installed. Run: pip install openai",
                ) from e

            api_key = self._get_api_key()
            if not api_key:
                raise ProviderError(
                    self.name,
                    f"Missing API key for provider '{self.name}'",
                )

            self._client = openai.AsyncOpenAI(
                api_key=api_key,
                base_url=self.base_url,
                timeout=self.timeout,
            )
        return self._client

    async def chat(
        self,
        model: str,
        messages: list[dict],
        *,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> LLMResponse:
        """Send a chat-completions request via the OpenAI SDK."""
        client = self._get_client()
        start = time.perf_counter()

        try:
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
        except Exception as e:
            status = getattr(e, "status_code", None)
            raise ProviderError(
                self.name,
                f"chat() failed for model '{model}': {e}",
                status_code=status,
            ) from e

        latency_ms = (time.perf_counter() - start) * 1000.0

        text = response.choices[0].message.content or "" if response.choices else ""
        usage = response.usage
        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0
        total_tokens = usage.total_tokens if usage else (prompt_tokens + completion_tokens)
        cost = estimate_llm_cost(model, prompt_tokens, completion_tokens)

        return LLMResponse(
            text=text,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            estimated_cost=cost,
        )

    @abstractmethod
    def get_models(self) -> list[str]:
        """Return the model IDs served by this provider."""
        raise NotImplementedError

    async def health_check(self) -> bool:
        """Probe by listing models. Returns True if the call succeeds."""
        try:
            client = self._get_client()
            await client.models.list()
            return True
        except Exception:
            return False

    async def close(self) -> None:
        """Close the async client if open."""
        if self._client is not None:
            try:
                await self._client.close()
            except Exception:
                pass
            self._client = None
