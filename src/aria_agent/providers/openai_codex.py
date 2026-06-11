"""OpenAI Codex (OAuth) provider.

Endpoint: https://api.openai.com/v1 (OpenAI-compatible chat completions)
Auth: OAuth token via OPENAI_CODEX_OAUTH_TOKEN env var. Tokens refresh automatically
per the model-router prefs — the user does not use the direct OpenAI API key path.

Active Codex pool (per model-router skill):
- gpt-5.5 (latest frontier, OAuth-only)
- gpt-5.4-mini (small/fast — listed as the M3 fallback chain's 2nd step
  on 2026-06-10; not yet verified live on this plan — the OAuth token
  isn't configured. When OPENAI_CODEX_OAUTH_TOKEN is set, this model
  is the planned 2nd fallback in the M3 chain: minimax-direct / MiniMax-M3
  → opencode-go / minimax-m3 → openai-codex / gpt-5.4-mini.)

Other Codex models (codex-mini-latest, gpt-5.4, gpt-5.3-codex, etc.) are
intentionally excluded by the user per the active-pool rules in the
model-router skill.
"""
import os
from typing import Optional

from .openai_compatible import OpenAICompatibleProvider


# Active Codex pool (per model-router skill). Add to this only after OAuth validation.
# gpt-5.4-mini is the documented 2nd fallback in the M3 chain
# (see aria_agent/router/routing_table.py — MiniMax-M3's fallback_chain).
# Live verification is blocked on a missing OPENAI_CODEX_OAUTH_TOKEN.
OPENAI_CODEX_MODELS: list[str] = [
    "gpt-5.5",
    "gpt-5.4-mini",
]


class OpenAICodexProvider(OpenAICompatibleProvider):
    """Provider for OpenAI Codex (OAuth-authenticated).

    Env var: `OPENAI_CODEX_OAUTH_TOKEN` (the OAuth bearer, not a direct API key).
    The token is refreshed by the OAuth client; this provider just consumes it.
    """

    base_url: str = "https://api.openai.com/v1"

    def __init__(self, *, oauth_token: Optional[str] = None, timeout: float = 60.0):
        super().__init__(name="openai-codex", timeout=timeout)
        self._explicit_token = oauth_token

    def _get_api_key(self) -> str:
        if self._explicit_token:
            return self._explicit_token
        return os.environ.get("OPENAI_CODEX_OAUTH_TOKEN", "")

    def get_models(self) -> list[str]:
        return list(OPENAI_CODEX_MODELS)
