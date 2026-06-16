from shared_core.config import BaseAppConfig


class AppConfig(BaseAppConfig):
    """Project-specific configuration extending the shared core settings."""

    APP_NAME: str = "hermes-agent-framework"

    # Agent behaviour
    AGENT_MAX_STEPS: int = 5
    # "free_running" executes safe + risky tools directly; "approval_gated"
    # routes risky tool calls into the approval queue first.
    AGENT_MODE: str = "free_running"
    AGENT_ROUTING: str = "auto"  # "auto" | "llm" | "keyword"
    APPROVAL_TIMEOUT_SECONDS: float = 300.0

    # Database availability probe — connect timeout (seconds) before the service
    # falls back to in-memory stores. Keep this short so startup never hangs.
    DB_PROBE_TIMEOUT: int = 2
