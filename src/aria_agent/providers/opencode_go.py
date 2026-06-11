"""OpenCode Go (OCG) provider.

Endpoint: https://opencode.ai/zen/go/v1 (mixed protocol — chat-completions for
Kimi/MiniMax/mimo, Anthropic Messages for Qwen 3.7).
Auth: Bearer token via OPENCODE_GO_API_KEY env var.

This is the user's primary open-weights route. It serves the most models
(Kimi K2.6, Kimi K2.5, MiniMax M2.7, MiniMax M2.5, Qwen 3.7, MiMo V2.5, etc.)
through a single API key.

Two protocol paths are required because OCG doesn't normalize on one:
- chat_completions(): used by Kimi, MiniMax, mimo, Qwen 3.6
- messages(): used by Qwen 3.7 (Anthropic SDK protocol)

Pitfall: OCG's /models endpoint can 403 with Cloudflare 1010 (browser-signature
block). Use a browser-like User-Agent on direct curl probes. The OpenAI/Anthropic
SDKs do not trigger this for chat calls; the issue is inventory/probe calls.
"""
import os
import time
from typing import Any, Optional

from shared_core.llm import LLMResponse, estimate_llm_cost

from .base import BaseProvider, ProviderError


# Models served by OCG, grouped by protocol path.
# - chat_completions: OpenAI-compatible chat completions
# - anthropic_messages: Anthropic Messages API (Anthropic SDK base URL /zen/go)
#
# Verified-live on the user's $1/mo Go plan (probed 2026-06-10).
# These are the model IDs the API accepts on this plan — anything not in
# these lists returns "Model X is not supported" at call time, even though
# the OCG provider's wider catalog lists more.
OCG_CHAT_COMPLETIONS_MODELS: list[str] = [
    "kimi-k2.6",
    "kimi-k2.5",
    "minimax-m3",      # M3 mirror (lowercase-hyphen, verified live 2026-06-10)
    "minimax-m2.7",
    "minimax-m2.5",
    "mimo-v2.5",
    "mimo-v2.5-pro",
    # qwen-3.6-plus, qwen-3.6-max, qwen-3.7-plus, qwen-3.7-max,
    # and nemotron-3-ultra-550b-a55b are in OCG's wider catalog but are
    # NOT callable on this plan (probed: "Model X is not supported").
    # Listed in the routing table as Pro+/future so the registry can fall
    # back gracefully if the user upgrades.
]

# Models that need the Anthropic SDK path (different base URL, different auth).
# Per the model-router quirks file: Qwen 3.7 max uses /v1/messages, x-api-key.
# Currently EMPTY on this plan — qwen-3.7-max is in the catalog but not callable.
# If the user upgrades and it becomes live, add it here.
OCG_ANTHROPIC_MESSAGES_MODELS: list[str] = [
    # "qwen-3.7-max",  # Pro+ on this plan — see comment above
]


class _OCGAnthropicSubprovider:
    """Anthropic-Messages-protocol sub-provider for Qwen 3.7.

    OCG exposes some models through the Anthropic Messages API even though the
    rest of the catalog uses OpenAI-compatible chat completions. The base URL
    for the Anthropic SDK is /zen/go (no /v1; the SDK appends /v1/messages).
    Auth is x-api-key instead of Bearer.
    """

    def __init__(self, parent: "OpenCodeGoProvider"):
        self._parent = parent
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                import anthropic  # type: ignore
            except ImportError as e:
                raise ProviderError(
                    self._parent.name,
                    "anthropic SDK not installed. Run: pip install anthropic",
                ) from e

            api_key = self._parent._get_api_key()
            if not api_key:
                raise ProviderError(
                    self._parent.name,
                    "Missing OPENCODE_GO_API_KEY for OCG Anthropic route",
                )

            # Critical: base URL is /zen/go (no /v1) — SDK appends /v1/messages.
            self._client = anthropic.AsyncAnthropic(
                api_key=api_key,
                base_url="https://opencode.ai/zen/go",
            )
        return self._client

    async def messages(
        self,
        model: str,
        messages: list[dict],
        *,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        **kwargs,
    ) -> LLMResponse:
        client = self._get_client()
        start = time.perf_counter()

        try:
            response = await client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=messages,
                **kwargs,
            )
        except Exception as e:
            status = getattr(e, "status_code", None) or getattr(e, "status", None)
            raise ProviderError(
                self._parent.name,
                f"messages() failed for model '{model}': {e}",
                status_code=status,
            ) from e

        latency_ms = (time.perf_counter() - start) * 1000.0
        text = response.content[0].text if response.content else ""
        prompt_tokens = response.usage.input_tokens
        completion_tokens = response.usage.output_tokens
        total_tokens = prompt_tokens + completion_tokens
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


class OpenCodeGoProvider(BaseProvider):
    """OCG provider with both chat-completions and Anthropic-Messages paths.

    Single API key, two protocol families. The router picks the right sub-path
    based on the model.

    Env var: `OPENCODE_GO_API_KEY`.
    """

    base_url: str = "https://opencode.ai/zen/go/v1"

    def __init__(self, *, api_key: Optional[str] = None, timeout: float = 60.0):
        super().__init__(name="opencode-go")
        self._explicit_api_key = api_key
        self._chat_base_url = self.base_url
        self._chat_timeout = timeout
        # Cached async clients, built lazily.
        self._chat_client: Any = None
        self._anthropic = _OCGAnthropicSubprovider(self)

    def _get_api_key(self) -> str:
        if self._explicit_api_key:
            return self._explicit_api_key
        return os.environ.get("OPENCODE_GO_API_KEY", "")

    def _get_chat_client(self) -> Any:
        # Lazy: build an AsyncOpenAI client pointed at OCG.
        if self._chat_client is None:
            try:
                import openai  # type: ignore
            except ImportError as e:
                raise ProviderError(
                    self.name, "openai SDK not installed. Run: pip install openai"
                ) from e
            api_key = self._get_api_key()
            if not api_key:
                raise ProviderError(self.name, "Missing OPENCODE_GO_API_KEY")
            self._chat_client = openai.AsyncOpenAI(
                api_key=api_key, base_url=self._chat_base_url, timeout=self._chat_timeout
            )
        return self._chat_client

    async def chat(
        self,
        model: str,
        messages: list[dict],
        *,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> LLMResponse:
        """Route to chat-completions or Anthropic Messages based on the model.

        OCG exposes some models only through the Anthropic Messages API even
        though the rest of the catalog uses OpenAI-compatible chat completions.
        The split is per-model, not per-provider.
        """
        if model in OCG_ANTHROPIC_MESSAGES_MODELS:
            return await self._anthropic.messages(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs,
            )

        # Default: OpenAI-compatible chat completions.
        client = self._get_chat_client()
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

    def get_models(self) -> list[str]:
        return list(OCG_CHAT_COMPLETIONS_MODELS) + list(OCG_ANTHROPIC_MESSAGES_MODELS)

    async def health_check(self) -> bool:
        """Probe via the chat-completions client (cheaper than Anthropic)."""
        try:
            client = self._get_chat_client()
            await client.models.list()
            return True
        except Exception:
            return False

    async def close(self) -> None:
        if self._chat_client is not None:
            try:
                await self._chat_client.close()
            except Exception:
                pass
            self._chat_client = None
        # Anthropic client has its own close; try it best-effort.
        if self._anthropic._client is not None:
            try:
                await self._anthropic._client.close()
            except Exception:
                pass
            self._anthropic._client = None
