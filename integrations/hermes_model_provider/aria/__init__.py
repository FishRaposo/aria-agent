"""Hermes model-provider plugin for Aria.

Install by copying this directory to:
  ~/.hermes/plugins/model-providers/aria/

Then run Aria locally and select:
  hermes chat --provider aria -m aria/auto -q "..."

Aria exposes an OpenAI-compatible facade at /v1/chat/completions. The model IDs
here are virtual routing policies, not concrete upstream models.
"""
from __future__ import annotations

import os
from typing import Any

from providers import register_provider
from providers.base import ProviderProfile


class AriaProfile(ProviderProfile):
    """Aria local/router provider profile."""

    def build_extra_body(self, *, model: str | None = None, **context: Any) -> dict[str, Any]:
        # Leave an extension point for future Aria-specific metadata without
        # requiring Hermes core changes.
        body: dict[str, Any] = {}
        if model:
            body["aria_virtual_model"] = model
        return body


aria = AriaProfile(
    name="aria",
    aliases=("aria-router", "aria-model-selector"),
    api_mode="chat_completions",
    env_vars=("ARIA_API_KEY",),  # Local deployments can set ARIA_API_KEY=local-aria.
    base_url=os.environ.get("ARIA_BASE_URL", "http://127.0.0.1:8000/v1"),
    models_url=os.environ.get("ARIA_MODELS_URL", "http://127.0.0.1:8000/v1/models"),
    auth_type="api_key",
    fallback_models=(
        "aria/auto",
        "aria/coding",
        "aria/reasoning",
        "aria/cheap",
        "aria/quality",
        "aria/route",
        "aria/role/planner",
        "aria/role/implementer",
        "aria/role/reviewer",
        "aria/role/researcher",
    ),
    default_aux_model="aria/auto",
)

register_provider(aria)
