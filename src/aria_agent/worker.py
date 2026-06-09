from shared_core.tasks import create_celery_app

from .config import AppConfig

config = AppConfig()
celery_app = create_celery_app(
    config.APP_NAME,
    broker_url=config.CELERY_BROKER_URL,
    backend_url=config.CELERY_RESULT_BACKEND,
)


@celery_app.task
def run_agent_task(user_query: str, session_id: str = "") -> dict:
    """Async task: run agent with tool execution."""
    from .agents import AriaAgent
    from .approvals import ApprovalGate
    from .tools import ToolRegistry

    registry = ToolRegistry()
    gate = ApprovalGate()
    agent = AriaAgent(registry, gate)
    response = agent.run(user_query)
    return {"session_id": session_id, "response": response}
