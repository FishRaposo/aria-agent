from fastapi import FastAPI
from pydantic import BaseModel
from shared_core.database import DatabaseManager
from shared_core.errors import BaseApplicationError, application_error_handler
from shared_core.health import check_health
from shared_core.logging import setup_logging
from shared_core.redis import RedisManager

from .agents import AriaAgent
from .approvals import ApprovalGate
from .config import AppConfig
from .costs import CostTracker
from .tools import (
    CalculatorInput,
    EmailDraftInput,
    FileReaderInput,
    TaskCreatorInput,
    ToolRegistry,
    WebSearchInput,
    calculator,
    email_draft,
    file_reader,
    task_creator,
    web_search,
)
from .tracing import TraceLog

config = AppConfig()
setup_logging(level=config.LOG_LEVEL, service_name=config.APP_NAME)

app = FastAPI(title=config.APP_NAME, version="0.1.0")
db_manager = DatabaseManager(
    config.DATABASE_URL,
    pool_size=config.DB_POOL_SIZE,
    max_overflow=config.DB_MAX_OVERFLOW,
    pool_timeout=config.DB_POOL_TIMEOUT,
)
redis_manager = RedisManager(config.REDIS_URL)

app.add_exception_handler(BaseApplicationError, application_error_handler)

registry = ToolRegistry()
registry.register("calculator", CalculatorInput)(calculator)
registry.register("web_search", WebSearchInput)(web_search)
registry.register("file_reader", FileReaderInput)(file_reader)
registry.register("task_creator", TaskCreatorInput)(task_creator)
registry.register("email_draft", EmailDraftInput)(email_draft)

gate = ApprovalGate()
cost_tracker = CostTracker()
agent = AriaAgent(registry, gate, max_steps=5)

_run_history: dict[str, dict] = {}


class ChatRequest(BaseModel):
    message: str


class ApprovalItem(BaseModel):
    run_id: str
    action: str
    parameters: dict


_pending_approvals: list[ApprovalItem] = []


@app.post("/agent/chat")
def chat(req: ChatRequest):
    import uuid

    trace = TraceLog()
    run_id = str(uuid.uuid4())[:8]

    response = agent.run(req.message, trace=trace, cost_tracker=cost_tracker)
    trace_summary = trace.summary()
    cost_summary = cost_tracker.summary()

    _run_history[run_id] = {
        "query": req.message,
        "response": response,
        "trace": trace_summary,
        "cost": cost_summary,
    }

    return {
        "run_id": run_id,
        "reply": response,
        "trace": trace_summary,
        "cost": cost_summary,
    }


@app.get("/agent/trace/{run_id}")
def get_trace(run_id: str):
    if run_id not in _run_history:
        from fastapi.exceptions import HTTPException
        raise HTTPException(404, f"Run '{run_id}' not found")
    return _run_history[run_id]


@app.get("/tools")
def list_tools():
    return {"tools": registry.list_tools()}


@app.get("/tools/{name}")
def get_tool_schema(name: str):
    try:
        return registry.get_schema(name)
    except KeyError as e:
        from fastapi.exceptions import HTTPException
        raise HTTPException(404, f"Tool '{name}' not found") from e


@app.get("/health")
def health_check():
    return check_health(db_manager, redis_manager, config.APP_NAME)
