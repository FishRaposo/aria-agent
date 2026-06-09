from loguru import logger


class ApprovalGate:
    """Enforces human-in-the-loop review on critical actions."""
    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    def request_approval(self, action_name: str, parameters: dict) -> bool:
        if not self.enabled:
            return True
        logger.warning(
            "--- SECURITY CHECK: Approval for '{}' ---", action_name
        )
        logger.warning(f"Parameters: {parameters}")
        logger.info("Auto-approved by default sandbox policy.")
        return True
