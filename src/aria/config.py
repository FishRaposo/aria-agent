from urllib.parse import urlsplit

from pydantic import field_validator

from aria.internal.vendor_core.config import BaseAppConfig


class AppConfig(BaseAppConfig):
    """ARIA-specific configuration layered over the vendored base settings."""

    APP_NAME: str = "aria-agent-framework"
    # Browser access is opt-in; never inherit the vendor's wildcard default.
    CORS_ALLOWED_ORIGINS: str = ""

    @field_validator("CORS_ALLOWED_ORIGINS")
    @classmethod
    def explicit_cors_origins(cls, value: str) -> str:
        if not value.strip():
            return ""
        origins = [origin.strip() for origin in value.split(",")]
        for origin in origins:
            parsed = urlsplit(origin)
            # Accessing port also validates numeric/range syntax. An origin is
            # just scheme/host/port, never a wildcard, URL path or credentials.
            _ = parsed.port
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path
                or parsed.query
                or parsed.fragment
                or "*" in origin
                or "\\" in origin
                or any(character.isspace() for character in origin)
                or parsed.netloc.endswith(":")
            ):
                raise ValueError(
                    "CORS_ALLOWED_ORIGINS must list explicit HTTP(S) origins"
                )
        return ",".join(dict.fromkeys(origins))

    # Agent behaviour
    AGENT_MAX_STEPS: int = 5
    # "free_running" executes safe + risky tools directly; "approval_gated"
    # routes risky tool calls into the approval queue first.
    AGENT_MODE: str = "free_running"
    AGENT_ROUTING: str = "auto"  # "auto" | "llm" | "keyword"
    APPROVAL_TIMEOUT_SECONDS: float = 300.0

    # Expanded local execution policies. Defaults preserve the original
    # single-step, no-rate-limit, no-retry behavior.
    ARIA_PLANNING_MODE: str = "single"  # single | multi
    ARIA_SAFETY_MODE: str = "warn"  # off | warn | block
    ARIA_TOOL_RETRY_POLICIES: str = "{}"  # JSON mapping tool -> policy
    ARIA_RATE_LIMIT_PER_TOOL: int = 0  # 0 disables local limiting
    ARIA_RATE_LIMIT_WINDOW_SECONDS: float = 60.0
    ARIA_APPROVAL_SWEEPER_ENABLED: bool = False
    ARIA_MEMORY_RETRIEVAL_ENABLED: bool = False

    # Database availability probe — connect timeout (seconds) before the service
    # falls back to in-memory stores. Keep this short so startup never hangs.
    DB_PROBE_TIMEOUT: int = 2
