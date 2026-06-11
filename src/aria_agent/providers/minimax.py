"""MiniMax direct API provider.

Endpoint: https://api.minimax.io/v1 (OpenAI-compatible chat completions)
Auth: Bearer token via MiniMax_API_KEY env var
Models: MiniMax-M3 (default), MiniMax-M2.7, MiniMax-M2.5, MiniMax-M2.1, MiniMax-M2

Per model-router skill: MiniMax-M3 is the user's everyday default (tolerant rate limits,
native multimodality, 1M context). Other MiniMax models are also routable.
"""
import os
from typing import Optional

from .openai_compatible import OpenAICompatibleProvider


# Models served by MiniMax direct (per the model-router catalog 2026-06).
# M3 is the active default; M2.x are legacy (kept for fallback).
MINIMAX_DIRECT_MODELS: list[str] = [
    "MiniMax-M3",
    "MiniMax-M2.7",
    "MiniMax-M2.5",
    "MiniMax-M2.1",
    "MiniMax-M2",
]


class MiniMaxProvider(OpenAICompatibleProvider):
    """Provider for the user's direct MiniMax API key.

    Env var: `MiniMax_API_KEY` (or pass `api_key` explicitly to the constructor).
    """

    base_url: str = "https://api.minimax.io/v1"

    def __init__(self, *, api_key: Optional[str] = None, timeout: float = 60.0):
        super().__init__(name="minimax-direct", timeout=timeout)
        self._explicit_api_key = api_key

    def _get_api_key(self) -> str:
        if self._explicit_api_key:
            return self._explicit_api_key
        return os.environ.get("MiniMax_API_KEY", "")

    def get_models(self) -> list[str]:
        return list(MINIMAX_DIRECT_MODELS)
