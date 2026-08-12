"""ARIA agent LLM client — offline-first, real-when-keyed.

Mirrors ``llm-cost-latency-monitor/src/llm_monitor/sdk.py``: a ``mocked_response``
short-circuits to a deterministic simulated response (no network, no keys),
otherwise the real provider path runs via ``shared_core.llm.LLMClientFactory``
with a graceful fallback to mock mode on ImportError / no key / any failure. The
returned telemetry feeds the run's ``CostTracker``.
"""

import time
from typing import Any, Dict, Optional

from loguru import logger
from shared_core.pricing import calculate_cost


class AgentLLMClient:
    """Thin LLM wrapper used by the router and response generator."""

    def __init__(self, api_keys: Optional[Dict[str, str]] = None):
        self.api_keys = api_keys or {}

    def generate(
        self,
        model: str,
        prompt: str,
        mocked_response: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 512,
    ) -> Dict[str, Any]:
        """Return ``{"response": str, "telemetry": dict}``."""
        start = time.time()
        error: Optional[str] = None

        if mocked_response is not None:
            time.sleep(0.01)
            text = mocked_response
            input_tokens = max(1, len(prompt) // 4)
            output_tokens = max(1, len(text) // 4)
        else:
            try:
                text, input_tokens, output_tokens = self._call_real(
                    model, prompt, temperature, max_tokens
                )
            except ImportError:
                logger.warning("LLM SDK/key unavailable — falling back to mock mode")
                time.sleep(0.01)
                text = f"Mock response for: {prompt[:50]}..."
                input_tokens = max(1, len(prompt) // 4)
                output_tokens = max(1, len(text) // 4)
            except Exception as exc:  # noqa: BLE001 - record, never crash caller
                error = f"{type(exc).__name__}: {exc}"
                logger.error("LLM call failed for {}: {}", model, error)
                text = ""
                input_tokens = max(1, len(prompt) // 4)
                output_tokens = 0

        latency_ms = (time.time() - start) * 1000.0
        cost = calculate_cost(model, input_tokens, output_tokens)
        telemetry = {
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost,
            "latency_ms": latency_ms,
            "error": error,
        }
        return {"response": text, "telemetry": telemetry}

    def _call_real(self, model: str, prompt: str, temperature: float, max_tokens: int):
        """Invoke the real provider via shared_core. Raises on no SDK / no key."""
        import asyncio

        from shared_core.llm import LLMClientFactory

        openai_key = self.api_keys.get("openai")
        anthropic_key = self.api_keys.get("anthropic")
        is_anthropic = "claude" in model.lower()
        if is_anthropic and not anthropic_key:
            raise ImportError("No Anthropic API key configured")
        if not is_anthropic and not openai_key:
            raise ImportError("No OpenAI API key configured")

        factory = LLMClientFactory(
            openai_api_key=openai_key, anthropic_api_key=anthropic_key
        )
        if is_anthropic:
            response = asyncio.run(
                factory.generate_anthropic(
                    model, prompt, temperature=temperature, max_tokens=max_tokens
                )
            )
        else:
            response = asyncio.run(
                factory.generate_openai(
                    model, prompt, temperature=temperature, max_tokens=max_tokens
                )
            )
        return response.text, response.prompt_tokens, response.completion_tokens
