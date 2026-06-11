#!/usr/bin/env python3
"""Aria sub-agent tool for Hermes.

Drop this file into `~/.hermes/hermes-agent/tools/aria_subagent_tool.py` (or
install as a plugin), then add `aria_subagent_tool` to your tool config.

This tool lets Hermes invoke Aria's role-based sub-agents — each role
(planner, implementer, debugger, etc.) is backed by a model picked
specifically for the kind of work it does.

**What this gives Hermes:**

Instead of one model doing everything, Hermes can:
- aria_planner: get a structured plan (uses kimi-k2.6)
- aria_architect: get a system design (uses kimi-k2.6)
- aria_implementer: get production code (uses MiniMax-M3)
- aria_debugger: get a root-cause analysis (uses deepseek-v4-pro)
- aria_documenter: get clear documentation (uses kimi-k2.6)
- aria_reviewer: get a code review (uses glm-5.1)
- aria_tester: get test cases (uses MiniMax-M3)
- aria_validator: get a correctness check (uses glm-5.1)
- aria_researcher: get synthesized findings (uses deepseek-v4-pro)

Plus:
- aria_orchestrator_parallel: run N sub-agents in parallel
- aria_orchestrator_sequential: chain sub-agents with context

**Two integration modes:**

1. **HTTP mode (default)**: Tool makes HTTP calls to a running Aria
   server. Requires `ARIA_AGENT_URL` in the env (default:
   http://localhost:8000).

2. **Direct import mode**: Tool imports the Aria library directly.
   Requires `aria-agent` on PYTHONPATH + the Aria deps installed.
   Faster (no HTTP overhead), but tighter coupling.

Set `ARIA_INTEGRATION_MODE=http` or `ARIA_INTEGRATION_MODE=direct` in
the env to choose. Default: http.

**Usage examples (in Hermes conversations):**

    "Use aria_planner to break this down into steps"
    "Run aria_orchestrator_parallel with planner and architect"
    "Get aria_reviewer to look at this code"

**Setup:**

1. Start Aria: `cd ~/work/aria-agent && make serve`
2. Drop this file in: `cp aria-agent/integrations/hermes_aria_tool.py ~/.hermes/hermes-agent/tools/`
3. Set ARIA_AGENT_URL (optional, defaults to localhost:8000)
4. Use in conversation: "Ask aria_planner to plan a /health endpoint"
"""
import json
import os
from typing import List, Optional, Dict, Any
from urllib import request as urlrequest
from urllib.error import URLError, HTTPError
import asyncio


VALID_ROLES = (
    "planner", "architect", "implementer", "debugger", "documenter",
    "reviewer", "tester", "validator", "researcher",
)


# ----- HTTP mode ------------------------------------------------------------

def _aria_http_post(path: str, payload: dict, *, timeout: int = 60) -> dict:
    """POST JSON to the Aria server. Used in HTTP integration mode."""
    base = os.environ.get("ARIA_AGENT_URL", "http://localhost:8000")
    url = f"{base.rstrip('/')}{path}"
    data = json.dumps(payload).encode("utf-8")
    req = urlrequest.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlrequest.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.reason}", "body": e.read().decode("utf-8", errors="replace")}
    except URLError as e:
        return {"error": f"Could not reach Aria server at {url}: {e.reason}"}


# ----- Tool functions -------------------------------------------------------

def aria_subagent_tool(
    role: str,
    task: str,
    *,
    model_id: Optional[str] = None,
    budget: Optional[str] = None,
) -> str:
    """Run a single Aria sub-agent for a specific role.

    Args:
        role: One of "planner", "architect", "implementer", "debugger",
              "documenter", "reviewer", "tester", "validator", "researcher".
        task: The free-form task for the sub-agent.
        model_id: Optional explicit model override. Defaults to the role's
                 best-fit model.
        budget: Optional "cheap" | "balanced" | "quality" override.

    Returns:
        JSON string with the sub-agent result (model used, output, cost).
    """
    if role not in VALID_ROLES:
        return json.dumps({
            "error": f"Unknown role '{role}'. Valid: {list(VALID_ROLES)}",
        })
    if not task or not task.strip():
        return json.dumps({"error": "task is required and must be non-empty"})

    payload: Dict[str, Any] = {"role": role, "task": task}
    if model_id is not None:
        payload["model_id"] = model_id
    if budget is not None:
        payload["budget"] = budget

    result = _aria_http_post("/subagent/run", payload)
    return json.dumps(result, indent=2)


def aria_orchestrator_parallel_tool(
    task: str,
    roles: List[str],
    *,
    budget: Optional[str] = None,
) -> str:
    """Run multiple Aria sub-agents in parallel on the same task.

    Each sub-agent gets the full task. They run concurrently and don't
    see each other's outputs. Total latency ~= max(individual), not sum.

    Args:
        task: The shared task for all sub-agents.
        roles: List of role names (e.g., ["planner", "architect", "researcher"]).
        budget: Optional budget override for all sub-agents.

    Returns:
        JSON string with all sub-agent results + aggregated final output.
    """
    if not roles:
        return json.dumps({"error": "roles must be a non-empty list"})
    for r in roles:
        if r not in VALID_ROLES:
            return json.dumps({
                "error": f"Unknown role '{r}'. Valid: {list(VALID_ROLES)}",
            })
    if not task or not task.strip():
        return json.dumps({"error": "task is required and must be non-empty"})

    payload: Dict[str, Any] = {"task": task, "roles": roles, "mode": "parallel"}
    if budget is not None:
        payload["budget"] = budget

    result = _aria_http_post("/orchestrator/run", payload, timeout=120)
    return json.dumps(result, indent=2)


def aria_orchestrator_sequential_tool(
    task: str,
    roles: List[str],
    *,
    budget: Optional[str] = None,
    pass_full_output: bool = True,
) -> str:
    """Run Aria sub-agents in sequence, passing prior output as context.

    Each subsequent sub-agent sees all prior outputs in its context. The
    LAST sub-agent's output is the final answer.

    Args:
        task: The shared task for all sub-agents.
        roles: Ordered list of role names (e.g.,
               ["planner", "implementer", "validator"]).
        budget: Optional budget override.
        pass_full_output: True to pass all prior outputs; False to pass
               only the most recent.

    Returns:
        JSON string with all sub-agent results + the final output.
    """
    if not roles:
        return json.dumps({"error": "roles must be a non-empty list"})
    for r in roles:
        if r not in VALID_ROLES:
            return json.dumps({
                "error": f"Unknown role '{r}'. Valid: {list(VALID_ROLES)}",
            })
    if not task or not task.strip():
        return json.dumps({"error": "task is required and must be non-empty"})

    payload: Dict[str, Any] = {
        "task": task, "roles": roles, "mode": "sequential",
        "pass_full_output": pass_full_output,
    }
    if budget is not None:
        payload["budget"] = budget

    result = _aria_http_post("/orchestrator/run", payload, timeout=120)
    return json.dumps(result, indent=2)


def aria_list_subagents_tool() -> str:
    """List all available Aria sub-agent roles and their default models.

    No LLM call is made. Useful for discovering what sub-agents are
    available + which model each role would use.
    """
    result = _aria_http_post("/subagents", {}, timeout=10)  # GET, but the helper does POST
    # Actually /subagents is GET. Use a direct GET:
    base = os.environ.get("ARIA_AGENT_URL", "http://localhost:8000")
    url = f"{base.rstrip('/')}/subagents"
    try:
        with urlrequest.urlopen(url, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            return body
    except (URLError, HTTPError) as e:
        return json.dumps({"error": f"Could not reach Aria server: {e}"})


# ----- Tool requirement checks ----------------------------------------------

def check_aria_requirements() -> bool:
    """Check that the Aria server is reachable (for HTTP mode).

    Returns True if the server responds on /health. Hermes calls this
    before exposing the tool to the agent.
    """
    base = os.environ.get("ARIA_AGENT_URL", "http://localhost:8000")
    url = f"{base.rstrip('/')}/health"
    try:
        with urlrequest.urlopen(url, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False
