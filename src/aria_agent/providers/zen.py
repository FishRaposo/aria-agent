"""Zen provider — closed source models on the OpenCode Zen Pro tier.

Endpoint: https://opencode.ai/zen/v1
Auth: Bearer token via OPENCODE_GO_API_KEY env var (same key as OCG,
different base URL — Zen is the paid Pro tier; OCG `/zen/go/` is the
free Go tier).

**Scope: closed source models only.** The `OpenCodeGoProvider` handles
the open-weight catalog (Kimi K2, MiMo, DeepSeek, Hunyuan). Zen handles
the proprietary side (Claude, GPT, Gemini, Grok, MiniMax, GLM-5, Qwen
flagship). Same `OPENCODE_GO_API_KEY` authenticates against both
endpoints, but `/zen/v1/` is the path that exposes the closed source
catalog and (typically) requires paid Pro credits.

Models listed here are from the `/zen/v1/models` catalog probed
2026-06-11. On the user's $1/mo Go plan, calling most of these will
return 401 ``Insufficient balance`` — the routing table's
``fallback_chain`` is what handles that, walking to a callable model
when Zen rejects the call.

Pitfall: same as OCG — `/zen/v1/models` can 403 with Cloudflare 1010
(browser-signature block). The OpenAI/Anthropic SDKs avoid this for
chat calls; it's only the inventory/probe calls that hit it.
"""
import os
import time
from typing import Any, Optional

from shared_core.llm import LLMResponse, estimate_llm_cost

from .base import BaseProvider, ProviderError


# Closed source models served by Zen's /zen/v1/ endpoint.
# Probed 2026-06-11. On the user's $1/mo Go plan, calling most of these
# returns 401 "Insufficient balance" — the routing table's fallback_chain
# walks to a callable alternative.
ZEN_CHAT_COMPLETIONS_MODELS: list[str] = [
    # Anthropic
    "claude-fable-5",
    "claude-opus-4-8",
    "claude-opus-4-7",
    "claude-opus-4-6",
    "claude-opus-4-5",
    "claude-opus-4-1",
    "claude-sonnet-4-6",
    "claude-sonnet-4-5",
    "claude-sonnet-4",
    "claude-haiku-4-5",
    # Google
    "gemini-3.5-flash",
    "gemini-3.1-pro",
    "gemini-3-flash",
    # OpenAI
    "gpt-5.5",
    "gpt-5.5-pro",
    "gpt-5.4",
    "gpt-5.4-pro",
    "gpt-5.4-mini",
    "gpt-5.4-nano",
    "gpt-5.3-codex-spark",
    "gpt-5.3-codex",
    "gpt-5.2",
    "gpt-5.2-codex",
    "gpt-5.1",
    "gpt-5.1-codex-max",
    "gpt-5.1-codex",
    "gpt-5.1-codex-mini",
    "gpt-5",
    "gpt-5-codex",
    "gpt-5-nano",
    # xAI
    "grok-build-0.1",
    # Closed Chinese (Zhipu GLM-5 is closed; Qwen flagship is closed;
    # MiniMax is closed)
    "glm-5.1",
    "glm-5",
    "minimax-m3",
    "minimax-m2.7",
    "minimax-m2.5",
    "qwen3.7-max",
    "qwen3.7-plus",
    "qwen3.6-plus",
    "qwen3.6-max",
    "qwen3.5-plus",
    # Other
    "big-pickle",
]

# Models on Zen that use the Anthropic Messages protocol. Currently
# none — Zen's catalog is all chat-completions. (OCG used the Anthropic
# path for Qwen 3.6/3.7, but those are on Zen now and Zen normalizes
# on chat-completions.)
ZEN_ANTHROPIC_MESSAGES_MODELS: list[str] = []


class _ZenAnthropicSubprovider:
    """Anthropic-Messages-protocol sub-provider (placeholder for parity with OCG)."""

    def __init__(self, parent: "ZenProvider"):
        self._parent = parent
        self._client: Any = None

    async def messages(self, *args, **kwargs):  # pragma: no cover
        raise ProviderError(
            self._parent.name,
            "ZenProvider has no Anthropic-protocol models; use chat()",
        )


class ZenProvider(BaseProvider):
    """Zen (closed source) provider. Same OPENCODE_GO_API_KEY, but
    base URL is `/zen/v1/` (paid Pro tier) instead of `/zen/go/v1/`
    (free Go tier).

    Env var: `OPENCODE_GO_API_KEY`.
    """

    base_url: str = "https://opencode.ai/zen/v1"

    def __init__(self, *, api_key: Optional[str] = None, timeout: float = 60.0):
        super().__init__(name="zen")
        self._explicit_api_key = api_key
        self._chat_base_url = self.base_url
        self._chat_timeout = timeout
        self._chat_client: Any = None
        self._anthropic = _ZenAnthropicSubprovider(self)

    def _get_api_key(self) -> str:
        if self._explicit_api_key:
            return self._explicit_api_key
        return os.environ.get("OPENCODE_GO_API_KEY", "")

    def _get_chat_client(self) -> Any:
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
        if model in ZEN_ANTHROPIC_MESSAGES_MODELS:
            return await self._anthropic.messages(
                model=model, messages=messages,
                max_tokens=max_tokens, temperature=temperature, **kwargs,
            )
        client = self._get_chat_client()
        start = time.perf_counter()
        try:
            response = await client.chat.completions.create(
                model=model, messages=messages,
                temperature=temperature, max_tokens=max_tokens, **kwargs,
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
            text=text, model=model,
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
            total_tokens=total_tokens, latency_ms=latency_ms, estimated_cost=cost,
        )

    def get_models(self) -> list[str]:
        return list(ZEN_CHAT_COMPLETIONS_MODELS) + list(ZEN_ANTHROPIC_MESSAGES_MODELS)

    async def health_check(self) -> bool:
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
