#!/usr/bin/env python3
"""Aria → Command Code bridge.

This wrapper makes Aria the model selector for Command Code's headless mode:

    aria-cmd "Review this diff for bugs"
    git diff | aria-cmd --role reviewer --plan

Flow:
1. Get the task from argv/stdin.
2. Ask Aria's /agent/route endpoint (or local Python router fallback) which
   model should handle it.
3. Map Aria's model ID to Command Code's model ID.
4. Execute `cmd --print ... -m ...`.

Command Code has no true provider/plugin API on the Go plan, so this wrapper is
Aria's primary integration surface for `cmd`.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_ARIA_URL = os.environ.get("ARIA_URL", "http://127.0.0.1:8000").rstrip("/")
REPO_ROOT = Path(__file__).resolve().parents[1]

ARIA_TO_CMD_MODEL: dict[str, str] = {
    "kimi-k2.6": "moonshotai/Kimi-K2.6",
    "kimi-k2.5": "moonshotai/Kimi-K2.5",
    "deepseek-v4-pro": "deepseek/deepseek-v4-pro",
    "deepseek-v4-flash": "deepseek/deepseek-v4-flash",
    "MiniMax-M3": "MiniMaxAI/MiniMax-M3",
    "minimax-m3": "MiniMaxAI/MiniMax-M3",
    "minimax-m2.7": "MiniMaxAI/MiniMax-M2.7",
    "minimax-m2.5": "MiniMaxAI/MiniMax-M2.5",
    "mimo-v2.5": "xiaomi/mimo-v2.5",
    "mimo-v2.5-pro": "xiaomi/mimo-v2.5-pro",
    "glm-5.1": "zai-org/GLM-5.1",
    "glm-5": "zai-org/GLM-5",
    "qwen3.7-max": "Qwen/Qwen3.7-Max",
    "qwen3.7-plus": "Qwen/Qwen3.7-Plus",
    "nemotron-3-ultra": "nvidia/nemotron-3-ultra-550b-a55b",
    "nvidia/nemotron-3-ultra-550b-a55b": "nvidia/nemotron-3-ultra-550b-a55b",
}

BUDGET_TO_CMD_MODEL = {
    "cheap": "xiaomi/mimo-v2.5",
    "quality": "moonshotai/Kimi-K2.6",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Route a Command Code task through Aria first")
    parser.add_argument("prompt", nargs="*", help="Task prompt. If omitted, stdin is used.")
    parser.add_argument("--aria-url", default=DEFAULT_ARIA_URL, help="Aria server URL")
    parser.add_argument("--cmd-bin", default=os.environ.get("CMD_BIN", "cmd"), help="Command Code binary")
    parser.add_argument("--model", help="Bypass Aria and force this Command Code model ID")
    parser.add_argument("--budget", choices=["cheap", "balanced", "quality"], help="Routing budget hint")
    parser.add_argument("--role", help="Routing role hint (planner, implementer, reviewer, etc.)")
    parser.add_argument("--max-turns", default=os.environ.get("ARIA_CMD_MAX_TURNS", "3"))
    parser.add_argument("--plan", action="store_true", help="Pass Command Code --plan")
    parser.add_argument("--auto-accept", action="store_true", help="Pass Command Code --auto-accept")
    parser.add_argument("--yolo", action="store_true", help="Pass Command Code --yolo")
    parser.add_argument("--add-dir", action="append", default=[], help="Pass --add-dir to cmd (repeatable)")
    parser.add_argument("--route-only", action="store_true", help="Print routing decision and exit")
    parser.add_argument("--dry-run", action="store_true", help="Print command instead of running it")
    args = parser.parse_args()

    task = _task_from_inputs(args.prompt)
    if not task.strip():
        print("aria-cmd: empty task", file=sys.stderr)
        return 2

    route = route_task(task, args.aria_url, budget=args.budget, role=args.role)
    cmd_model = args.model or command_code_model(route, budget=args.budget)

    if args.route_only:
        print(json.dumps({"cmd_model": cmd_model, "aria_route": route}, indent=2, ensure_ascii=False))
        return 0

    cmd = [args.cmd_bin, "--print", task, "-m", cmd_model, "--max-turns", str(args.max_turns)]
    for path in args.add_dir:
        cmd.extend(["--add-dir", path])
    if args.plan:
        cmd.append("--plan")
    if args.auto_accept:
        cmd.append("--auto-accept")
    if args.yolo:
        cmd.append("--yolo")

    if args.dry_run:
        print(json.dumps({"command": cmd, "aria_route": route}, indent=2, ensure_ascii=False))
        return 0

    return subprocess.call(cmd)


def _task_from_inputs(parts: list[str]) -> str:
    prompt = " ".join(parts).strip()
    stdin = ""
    if not sys.stdin.isatty():
        stdin = sys.stdin.read().strip()
    if prompt and stdin:
        return f"{prompt}\n\nContext from stdin:\n{stdin}"
    return prompt or stdin


def route_task(task: str, aria_url: str, *, budget: str | None = None, role: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"task": task}
    if budget and budget != "balanced":
        # The current /agent/route endpoint is no-cost and does not accept budget.
        # We still include budget in local fallback metadata and command mapping.
        payload["budget"] = budget
    if role:
        payload["role"] = role

    try:
        req = urllib.request.Request(
            f"{aria_url}/agent/route",
            data=json.dumps({"task": task}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            route = json.loads(resp.read().decode("utf-8"))
            route["source"] = "http"
            if budget:
                route["budget"] = budget
            if role:
                route["role"] = role
            return route
    except Exception as exc:
        route = _route_task_locally(task)
        route["source"] = "local"
        route["http_error"] = str(exc)
        if budget:
            route["budget"] = budget
        if role:
            route["role"] = role
        return route


def _route_task_locally(task: str) -> dict[str, Any]:
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from aria_agent.agent import AriaAgent  # type: ignore
    from aria_agent.approvals import ApprovalGate  # type: ignore
    from aria_agent.providers.registry import ProviderRegistry  # type: ignore
    from aria_agent.router.routing_table import get_default_routing_table  # type: ignore
    from aria_agent.router.selector import ModelSelector  # type: ignore
    from aria_agent.tools import ToolRegistry  # type: ignore

    selector = ModelSelector(get_default_routing_table())
    agent = AriaAgent(
        registry=ProviderRegistry(),
        router=selector,
        tool_registry=ToolRegistry(),
        approval_gate=ApprovalGate(enabled=False),
    )
    return agent.preview_route(task)


def command_code_model(route: dict[str, Any], *, budget: str | None = None) -> str:
    if budget in BUDGET_TO_CMD_MODEL:
        return BUDGET_TO_CMD_MODEL[budget]
    primary = route.get("primary") or {}
    candidates = [primary.get("model_id")]
    for key in ("fallback", "escalation"):
        value = route.get(key)
        if isinstance(value, dict):
            candidates.append(value.get("model_id"))
    for model_id in candidates:
        if model_id in ARIA_TO_CMD_MODEL:
            return ARIA_TO_CMD_MODEL[model_id]
    return "moonshotai/Kimi-K2.5"


if __name__ == "__main__":
    raise SystemExit(main())
