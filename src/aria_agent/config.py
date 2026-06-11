"""Project-specific configuration extending the shared core settings.

The base settings come from `shared_core.config.BaseAppConfig`. This file
adds the provider API keys and project-specific knobs.
"""
from shared_core.config import BaseAppConfig


class AppConfig(BaseAppConfig):
    """Aria Agent configuration.

    Reads from environment / .env via Pydantic. Provider API keys are optional
    — providers are only constructed if their key is set.
    """

    APP_NAME: str = "aria-agent"

    # Provider API keys (all optional — agent constructs only what's configured)
    OPENCODE_GO_API_KEY: str = ""
    MiniMax_API_KEY: str = ""
    OPENAI_CODEX_OAUTH_TOKEN: str = ""

    # Default cooperation pattern
    DEFAULT_COOPERATION_PATTERN: str = "cascade"
