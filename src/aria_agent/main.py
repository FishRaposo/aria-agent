"""FastAPI gateway for Aria Agent (v0.3).

**Endpoints:**

- POST /agent/run        — main endpoint, runs a task (tool or model path)
- POST /agent/route      — preview which model would be picked (no API call)
- GET  /agent/patterns   — list available cooperation patterns
- GET  /agent/intent     — preview which path (tool vs model) would run
- GET  /agent/tools      — list the registered v0.1 tools + schemas
- GET  /models           — list all routable models with metadata
- GET  /providers        — list configured providers + health status
- GET  /health           — overall health check

**Path dispatch:** `AriaAgent.run()` automatically picks the tool path
(KeywordRouterAgent, v0.1 preserved) or the model path (router +
cooperation pattern, v0.2). Callers can force a path with `force_mode`.

**Wiring (per-request safety):**

- `registry` (ProviderRegistry) — constructed once at startup, shared
- `router` (ModelSelector) — constructed once at startup, shared
- `tool_registry` (ToolRegistry) — built once with v0.1's 5 builtin tools
- `approval_gate` (ApprovalGate) — single instance, shared
- `agent` (AriaAgent) — constructed once, holds refs to all the above

No module-level mutable state per request. The agent is stateless w.r.t.
request data; per-request state (memory, trace, cost) is created inside
`AriaAgent._run_tool_path()`.
"""
import asyncio
import json
import time
import uuid
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field, field_validator
from shared_core.errors import BaseApplicationError, application_error_handler
from shared_core.logging import setup_logging

from .agent import AriaAgent
from .approvals import ApprovalGate
from .config import AppConfig
from .cooperation import CooperationResult
from .providers.registry import ProviderRegistry, get_default_registry
from .router.selector import ModelSelector
from .router.routing_table import get_default_routing_table
from .subagents import (
    OrchestrationResult,
    Orchestrator,
    SubAgent,
    SubAgentRegistry,
    get_default_sub_agent_registry,
)
from .tools import ToolRegistry
from .builtin_tools.calculator import CalculatorInput, calculator
from .builtin_tools.email_draft import EmailDraftInput, email_draft
from .builtin_tools.file_reader import FileReaderInput, file_reader
from .builtin_tools.task_creator import TaskCreatorInput, task_creator
from .builtin_tools.web_search import WebSearchInput, web_search


# ----- App startup ----------------------------------------------------------

config = AppConfig()
setup_logging(level=config.LOG_LEVEL, service_name=config.APP_NAME)

app = FastAPI(
    title=config.APP_NAME,
    version="0.4.0",
    description="Cross-provider model router with cooperation patterns, "
    "v0.1 tool agent preserved, and v0.4 sub-agents + orchestrator.",
)
app.add_exception_handler(BaseApplicationError, application_error_handler)


# Constructed ONCE at startup, shared across all requests. This is safe
# because the registry, router, and tool registry are stateless (no per-request
# data). The AriaAgent itself is also stateless w.r.t. request data — it
# creates per-request memory/trace/cost inside _run_tool_path.
registry: ProviderRegistry = get_default_registry()
router: ModelSelector = ModelSelector(get_default_routing_table())

# Build the v0.1 tool registry with the 5 builtin tools. This preserves
# ALL v0.1 functionality: calculator, web_search, file_reader, task_creator,
# email_draft. The tools run as fast, deterministic functions — no LLM call
# needed. The AriaAgent uses this when the query matches a tool keyword.
tool_registry = ToolRegistry()
tool_registry.register("calculator", CalculatorInput)(calculator)
tool_registry.register("web_search", WebSearchInput)(web_search)
tool_registry.register("file_reader", FileReaderInput)(file_reader)
tool_registry.register("task_creator", TaskCreatorInput)(task_creator)
tool_registry.register("email_draft", EmailDraftInput)(email_draft)

approval_gate = ApprovalGate(enabled=True)
agent = AriaAgent(
    registry=registry,
    router=router,
    tool_registry=tool_registry,
    approval_gate=approval_gate,
    default_pattern=config.DEFAULT_COOPERATION_PATTERN,
)

# v0.4 sub-agent system. Each role gets a model picked for the kind of
# work it does (planner → kimi-k2.6, debugger → deepseek-v4-pro, etc.).
# The orchestrator runs sub-agents in parallel or sequential chains.
sub_agent_registry: SubAgentRegistry = get_default_sub_agent_registry(registry, router)
orchestrator: Orchestrator = Orchestrator(sub_agent_registry)


# ----- Request / response models -------------------------------------------

class RunRequest(BaseModel):
    task: str = Field(..., description="The user's request (free-form text)")
    pattern: Optional[str] = Field(
        None, description="Cooperation pattern (model path): "
        "cascade | plan_execute_validate | ensemble"
    )
    budget: Optional[str] = Field(
        None, description="Budget override (model path): cheap | balanced | quality"
    )
    force_mode: Optional[str] = Field(
        None, description="Force a path: 'tool' or 'model'. Skips intent "
        "classification. Default: auto-classify."
    )

    @field_validator("task")
    @classmethod
    def _task_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("task must be non-empty")
        return v

    @field_validator("force_mode")
    @classmethod
    def _force_mode_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("tool", "model"):
            raise ValueError("force_mode must be 'tool' or 'model'")
        return v


class RunResponse(BaseModel):
    final_output: str
    pattern: str
    intent: str
    num_steps: int
    num_models_used: int
    total_cost_usd: float
    total_latency_ms: float
    steps: list[dict]
    metadata: dict


class RouteRequest(BaseModel):
    task: str = Field(..., description="The task to route (no API call)")


class RouteResponse(BaseModel):
    task_type: str
    primary: dict
    fallback: Optional[dict] = None
    escalation: Optional[dict] = None
    reason: str


class ChatMessage(BaseModel):
    """OpenAI-compatible chat message for /v1/chat/completions."""

    role: str
    content: Any


class ChatCompletionRequest(BaseModel):
    """Minimal OpenAI-compatible chat-completions request.

    Aria uses this compatibility surface to act as a model-selector provider
    for Hermes/OpenCode-like clients. It intentionally ignores most OpenAI
    knobs; routing happens from the task text + the virtual Aria model name.
    """

    model: str = Field("aria/auto", description="Virtual Aria route model")
    messages: list[ChatMessage]
    stream: bool = False
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None


class IntentRequest(BaseModel):
    task: str = Field(..., description="The task to classify")


class IntentResponse(BaseModel):
    intent: str
    matched_tool: Optional[str] = None
    matched_keyword: Optional[str] = None
    reason: str


# ---- v0.4 sub-agent + orchestrator models -----------------------------------

class SubAgentRunRequest(BaseModel):
    """Run a single sub-agent for a specific role."""
    role: str = Field(..., description="The sub-agent role: planner, architect, "
        "implementer, debugger, documenter, reviewer, tester, validator, researcher")
    task: str = Field(..., description="The task to run the sub-agent on")
    model_id: Optional[str] = Field(
        None, description="Override the role's default model. Useful for testing."
    )
    budget: Optional[str] = Field(
        None, description="Budget override: cheap | balanced | quality"
    )

    @field_validator("task")
    @classmethod
    def _task_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("task must be non-empty")
        return v


class SubAgentRunResponse(BaseModel):
    role: str
    model_id: str
    provider_name: str
    output_text: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    cost_usd: float
    success: bool
    error: Optional[str] = None
    metadata: dict


class OrchestratorRequest(BaseModel):
    """Run the orchestrator (parallel or sequential) over multiple sub-agents."""
    task: str = Field(..., description="The task for the sub-agents")
    roles: list[str] = Field(..., description="Sub-agent roles to run. "
        "Order matters for sequential mode; ignored for parallel.")
    mode: str = Field("parallel", description="'parallel' or 'sequential'")
    budget: Optional[str] = Field(None, description="Budget override")
    pass_full_output: bool = Field(
        True, description="Sequential mode: pass all prior outputs as context "
        "(True) or just the last one (False)"
    )

    @field_validator("task")
    @classmethod
    def _task_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("task must be non-empty")
        return v

    @field_validator("mode")
    @classmethod
    def _mode_valid(cls, v: str) -> str:
        if v not in ("parallel", "sequential"):
            raise ValueError("mode must be 'parallel' or 'sequential'")
        return v

    @field_validator("roles")
    @classmethod
    def _roles_not_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("roles must be a non-empty list")
        return v


class OrchestratorStepResponse(BaseModel):
    role: str
    model_id: str
    provider_name: str
    output_text: str
    latency_ms: float
    cost_usd: float
    success: bool
    error: Optional[str] = None
    step_index: int
    wall_clock_ms: float


class OrchestratorResponse(BaseModel):
    final_output: str
    mode: str
    num_steps: int
    num_models_used: int
    num_succeeded: int
    num_failed: int
    total_cost_usd: float
    total_latency_ms: float
    steps: list[OrchestratorStepResponse]
    metadata: dict


# ----- Endpoints ------------------------------------------------------------

@app.post("/agent/run", response_model=RunResponse)
async def agent_run(req: RunRequest) -> RunResponse:
    """Run a task. AriaAgent picks tool path or model path automatically.

    - Tool path: query matches a tool keyword → KeywordRouterAgent (v0.1)
    - Model path: query doesn't match a tool → router + cooperation pattern
    - Force mode: bypass classification with `force_mode="tool"|"model"`

    The full step transcript is included for debugging.
    """
    if req.pattern and req.pattern not in agent.list_patterns():
        raise HTTPException(
            400, f"Unknown pattern '{req.pattern}'. Available: {agent.list_patterns()}"
        )

    logger.info(
        f"agent.run: force_mode={req.force_mode}, "
        f"pattern={req.pattern or agent.default_pattern}, "
        f"budget={req.budget}, task={req.task[:80]}..."
    )

    try:
        result: CooperationResult = await agent.run(
            req.task,
            pattern=req.pattern,
            budget=req.budget,
            force_mode=req.force_mode,
        )
    except Exception as e:
        logger.exception("agent.run failed")
        raise HTTPException(500, f"Agent run failed: {e}") from e

    return RunResponse(
        final_output=result.final_output,
        pattern=result.pattern,
        intent=result.metadata.get("intent", "unknown"),
        num_steps=result.num_steps,
        num_models_used=result.num_models_used,
        total_cost_usd=result.total_cost_usd,
        total_latency_ms=result.total_latency_ms,
        steps=[_step_to_dict(s) for s in result.steps],
        metadata=result.metadata,
    )


@app.post("/agent/route", response_model=RouteResponse)
async def agent_route(req: RouteRequest) -> RouteResponse:
    """Preview which model the router would pick for a task (model path).

    No API calls are made. Useful for debugging and for clients that want
    to know the routing decision before committing to a run.
    """
    return RouteResponse(**agent.preview_route(req.task))


@app.post("/agent/intent", response_model=IntentResponse)
async def agent_intent(req: IntentRequest) -> IntentResponse:
    """Preview which path (tool vs model) would run for a task.

    No API calls are made. Useful for testing and for clients that want
    to know the dispatch decision before committing to a run.
    """
    classification = agent.classify_intent(req.task)
    return IntentResponse(
        intent=classification.intent.value,
        matched_tool=classification.matched_tool,
        matched_keyword=classification.matched_keyword,
        reason=classification.reason,
    )


@app.get("/agent/patterns")
def agent_patterns() -> dict:
    """List available cooperation patterns (model path)."""
    return {"patterns": agent.list_patterns(), "default": agent.default_pattern}


@app.get("/agent/tools")
def agent_tools() -> dict:
    """List the v0.1 builtin tools registered in the tool registry.

    Returns each tool's name, description, and JSON schema. The agent
    uses these to dispatch tool-path queries (no LLM call needed).
    """
    if agent.tool_registry is None:
        return {"tools": [], "count": 0, "message": "No tool registry wired."}
    return {
        "tools": agent.tool_registry.list_tools(),
        "count": len(agent.tool_registry.tools),
    }


# ---- v0.4 sub-agent + orchestrator endpoints -------------------------------

@app.get("/subagents")
def list_subagents() -> dict:
    """List all sub-agent roles, their default model picks, and specs.

    No API calls are made. The default model is computed via the role
    router (`select_for_role`), so this also serves as a "what model
    would this role use" preview.
    """
    from .router.routing_table import SubAgentRole

    roles_info = []
    for role in sub_agent_registry.list_roles():
        spec = sub_agent_registry.get_spec(role)
        # Compute the role's default model
        try:
            decision = router.select_for_role(role)
            default_model = {
                "provider": decision.primary.provider_name,
                "model_id": decision.primary.model_id,
                "tier": decision.primary.tier.value,
                "reason": decision.reason,
            }
        except Exception as e:
            default_model = {"error": str(e)}
        roles_info.append({
            "role": role.value,
            "description": spec.description,
            "temperature": spec.temperature,
            "max_tokens": spec.max_tokens,
            "default_model": default_model,
        })
    return {"subagents": roles_info, "count": len(roles_info)}


@app.post("/subagent/run", response_model=SubAgentRunResponse)
async def subagent_run(req: SubAgentRunRequest) -> SubAgentRunResponse:
    """Run a single sub-agent for a specific role.

    The sub-agent picks its model via the role router (or uses the
    model_id override). The result includes the model used, the
    output, and full cost/latency info.

    This is the simplest "right tool for the job" API: pick a role,
    give it a task, get a structured result.
    """
    from .router.routing_table import SubAgentRole

    # Validate role
    try:
        role = SubAgentRole(req.role)
    except ValueError:
        valid = [r.value for r in SubAgentRole]
        raise HTTPException(
            400, f"Unknown role '{req.role}'. Available: {valid}"
        )

    logger.info(
        f"subagent.run: role={role.value}, model_override={req.model_id}, "
        f"task={req.task[:80]}..."
    )

    # Build the sub-agent
    if req.model_id:
        sub_agent = SubAgent(
            role=role,
            registry=registry,
            router=router,
            model_id=req.model_id,
        )
    else:
        sub_agent = sub_agent_registry.get(role)
        if req.budget:
            # Re-pick with budget, but resolve through the registry so we
            # land on a *callable* model (the routing table's preferred
            # provider might not be registered in this environment —
            # e.g. on Termux with only OCG key, minimax-direct isn't in
            # the provider registry even though the routing table has M3).
            decision = router.select_for_role(role, budget=req.budget)
            _, picked_model_id = registry.resolve_decision(decision)
            sub_agent = SubAgent(
                role=role,
                registry=registry,
                router=router,
                model_id=picked_model_id,
            )

    try:
        result = await sub_agent.run(req.task)
    except Exception as e:
        logger.exception("subagent.run failed")
        raise HTTPException(500, f"Sub-agent run failed: {e}") from e

    return SubAgentRunResponse(
        role=result.role.value,
        model_id=result.model_id,
        provider_name=result.provider_name,
        output_text=result.output_text,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        latency_ms=result.latency_ms,
        cost_usd=result.cost_usd,
        success=result.success,
        error=result.error,
        metadata=result.metadata,
    )


@app.post("/orchestrator/run", response_model=OrchestratorResponse)
async def orchestrator_run(req: OrchestratorRequest) -> OrchestratorResponse:
    """Run the orchestrator over multiple sub-agents.

    Modes:
    - "parallel": asyncio.gather over all roles. Each sub-agent sees
      only the task. Total latency = max(individual latencies).
      Best for: independent perspectives (planner + architect + researcher).

    - "sequential": for-loop with prior output as context. Each
      sub-agent sees all prior outputs. Total latency = sum.
      Best for: dependent work (planner → implementer → validator).

    The roles list is the sub-agents to run. For parallel, order is
    irrelevant. For sequential, order matters (each gets the prior).
    """
    from .router.routing_table import SubAgentRole

    # Validate roles
    role_enums = []
    for r in req.roles:
        try:
            role_enums.append(SubAgentRole(r))
        except ValueError:
            valid = [rr.value for rr in SubAgentRole]
            raise HTTPException(
                400, f"Unknown role '{r}'. Available: {valid}"
            )

    logger.info(
        f"orchestrator.run: mode={req.mode}, roles={[r.value for r in role_enums]}, "
        f"task={req.task[:80]}..."
    )

    try:
        if req.mode == "parallel":
            result: OrchestrationResult = await orchestrator.run_parallel(
                req.task, role_enums, budget=req.budget,
            )
        else:  # sequential
            result = await orchestrator.run_sequential(
                req.task, role_enums, budget=req.budget,
                pass_full_output=req.pass_full_output,
            )
    except Exception as e:
        logger.exception("orchestrator.run failed")
        raise HTTPException(500, f"Orchestrator run failed: {e}") from e

    return OrchestratorResponse(
        final_output=result.final_output,
        mode=result.mode,
        num_steps=result.num_steps,
        num_models_used=result.num_models_used,
        num_succeeded=result.num_succeeded,
        num_failed=result.num_failed,
        total_cost_usd=result.total_cost_usd,
        total_latency_ms=result.total_latency_ms,
        steps=[
            OrchestratorStepResponse(
                role=s.role.value,
                model_id=s.result.model_id,
                provider_name=s.result.provider_name,
                output_text=s.result.output_text,
                latency_ms=s.result.latency_ms,
                cost_usd=s.result.cost_usd,
                success=s.result.success,
                error=s.result.error,
                step_index=s.step_index,
                wall_clock_ms=s.wall_clock_ms,
            )
            for s in result.steps
        ],
        metadata=result.metadata,
    )


@app.get("/v1/models")
def openai_compatible_models() -> dict:
    """OpenAI-compatible virtual model catalog for Aria-as-router.

    These are not concrete upstream models. They are routing policies exposed as
    model IDs so clients such as Hermes can set `provider=aria, model=aria/auto`
    and let Aria choose the real backend per request.
    """
    created = 1781137100
    models = [
        ("aria/auto", "Route from task text using Aria's task classifier"),
        ("aria/coding", "Bias routing toward implementation/coding models"),
        ("aria/reasoning", "Bias routing toward planning/reasoning models"),
        ("aria/cheap", "Force Aria's cheap-workhorse budget"),
        ("aria/quality", "Force Aria's best-quality budget"),
        ("aria/route", "Return the routing decision as JSON text; no model call"),
        ("aria/role/planner", "Run the planner sub-agent"),
        ("aria/role/implementer", "Run the implementer sub-agent"),
        ("aria/role/reviewer", "Run the reviewer sub-agent"),
        ("aria/role/researcher", "Run the researcher sub-agent"),
    ]
    return {
        "object": "list",
        "data": [
            {
                "id": model_id,
                "object": "model",
                "created": created,
                "owned_by": "aria",
                "description": description,
            }
            for model_id, description in models
        ],
    }


@app.post("/v1/chat/completions")
async def openai_compatible_chat(req: ChatCompletionRequest) -> dict:
    """OpenAI-compatible chat-completions facade.

    This is intentionally thin: it translates a chat request into Aria's existing
    route/run/sub-agent APIs and returns an OpenAI-shaped response. It gives
    external agents a provider-like integration point while keeping Aria's real
    logic in the router/sub-agent layers.
    """
    task = _messages_to_task(req.messages)
    if not task.strip():
        raise HTTPException(status_code=400, detail="No user task found in messages")

    model = (req.model or "aria/auto").strip().lower()
    budget = _budget_from_virtual_model(model)

    if model == "aria/route":
        payload = agent.preview_route(task)
        content = _json_dumps(payload)
        actual_model = payload["primary"]["model_id"]
    elif model.startswith("aria/role/"):
        role_name = model.rsplit("/", 1)[-1]
        try:
            from .router.routing_table import SubAgentRole
            role = SubAgentRole(role_name)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Unknown Aria role: {role_name}") from exc
        sub_agent = sub_agent_registry.get(role)
        result = await sub_agent.run(task)
        content = result.output_text
        actual_model = result.model_id
    else:
        force_mode = "model"
        result = await agent.run(task, budget=budget, force_mode=force_mode)
        content = result.final_output
        actual_model = result.steps[-1].model_id if result.steps else model

    now = int(time.time())
    completion_id = f"chatcmpl-aria-{uuid.uuid4().hex[:12]}"
    response = {
        "id": completion_id,
        "object": "chat.completion",
        "created": now,
        "model": req.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
        "aria": {
            "virtual_model": req.model,
            "actual_model": actual_model,
            "budget": budget or "balanced",
        },
    }
    if req.stream:
        return StreamingResponse(
            _stream_chat_completion(response),
            media_type="text/event-stream",
        )
    return response


@app.get("/models")
def list_models() -> dict:
    """List all routable models with metadata, grouped by provider."""
    table = get_default_routing_table()
    by_provider: dict[str, list[dict]] = {}
    for m in table.all():
        by_provider.setdefault(m.provider_name, []).append({
            "model_id": m.model_id,
            "tier": m.tier.value,
            "task_types": [t.value for t in m.task_types],
            "context_window": m.context_window,
            "cost_per_1m_input": m.cost_per_1m_input,
            "cost_per_1m_output": m.cost_per_1m_output,
            "terminal_bench_score": m.terminal_bench_score,
            "accepts_images": m.accepts_images,
            "notes": m.notes,
        })
    return {
        "total_models": len(table.all()),
        "active_pool_size": len(table.active_pool()),
        "by_provider": by_provider,
    }


@app.get("/providers")
async def list_providers() -> dict:
    """List configured providers with health status."""
    provider_names = registry.list_providers()
    health_results = await asyncio.gather(
        *[safe_health_check(registry, name) for name in provider_names],
        return_exceptions=True,
    )
    providers = []
    for name, healthy in zip(provider_names, health_results):
        if isinstance(healthy, Exception):
            healthy = False
        providers.append({"name": name, "healthy": bool(healthy)})
    return {"providers": providers, "count": len(providers)}


@app.get("/health")
def health_check() -> dict:
    """Overall health check."""
    return {
        "status": "healthy",
        "service": config.APP_NAME,
        "version": "0.4.0",
        "providers_configured": len(registry.list_providers()),
        "patterns_available": agent.list_patterns(),
        "tools_available": (
            len(agent.tool_registry.tools) if agent.tool_registry else 0
        ),
        "subagents_available": (
            len(sub_agent_registry.list_roles()) if sub_agent_registry else 0
        ),
    }


# ----- Helpers --------------------------------------------------------------

def _messages_to_task(messages: list[ChatMessage]) -> str:
    """Collapse OpenAI chat messages into the task text Aria should route.

    Prefer the last user message, but include preceding system/developer context
    as lightweight context so router decisions see constraints like "be cheap" or
    "this is a code review".
    """
    if not messages:
        return ""

    def _content_to_text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text") or item.get("content")
                    if text:
                        parts.append(str(text))
                else:
                    parts.append(str(item))
            return "\n".join(parts)
        return str(content)

    last_user = ""
    context_parts: list[str] = []
    for msg in messages:
        text = _content_to_text(msg.content).strip()
        if not text:
            continue
        role = msg.role.lower()
        if role == "user":
            last_user = text
        elif role in {"system", "developer"}:
            context_parts.append(f"{role}: {text}")

    if context_parts and last_user:
        return "\n\n".join([*context_parts, f"user: {last_user}"])
    return last_user or "\n".join(context_parts)


def _budget_from_virtual_model(model: str) -> Optional[str]:
    """Map virtual Aria model IDs to router budget knobs."""
    if model.endswith("/cheap") or model == "aria/cheap":
        return "cheap"
    if model.endswith("/quality") or model == "aria/quality":
        return "quality"
    return None


def _json_dumps(payload: Any) -> str:
    """Stable JSON text for route/explain virtual models."""
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


async def _stream_chat_completion(response: dict[str, Any]):
    """Yield a minimal OpenAI-compatible chat-completions stream.

    Hermes first attempts streaming for chat-completions providers. Aria's model
    selection is not token-streaming yet, but emitting one delta + [DONE] keeps
    OpenAI-compatible clients happy and avoids treating Aria as failed.
    """
    choice = response["choices"][0]
    content = choice["message"]["content"]
    chunk = {
        "id": response["id"],
        "object": "chat.completion.chunk",
        "created": response["created"],
        "model": response["model"],
        "choices": [
            {
                "index": 0,
                "delta": {"role": "assistant", "content": content},
                "finish_reason": None,
            }
        ],
    }
    done = {
        "id": response["id"],
        "object": "chat.completion.chunk",
        "created": response["created"],
        "model": response["model"],
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
    }
    yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
    yield f"data: {json.dumps(done, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"


def _step_to_dict(step) -> dict:
    """Convert a StepResult to a JSON-friendly dict."""
    return {
        "step_name": step.step_name,
        "provider": step.provider_name,
        "model": step.model_id,
        "output_text": step.output_text,
        "prompt_tokens": step.prompt_tokens,
        "completion_tokens": step.completion_tokens,
        "latency_ms": step.latency_ms,
        "cost_usd": step.cost_usd,
        "success": step.success,
        "error": step.error,
    }


async def safe_health_check(registry: ProviderRegistry, name: str) -> bool:
    """Run health check, returning False on any error."""
    try:
        provider = registry.get(name)
        return bool(await provider.health_check())
    except Exception:
        return False
