#!/usr/bin/env python3
"""Aria → OpenCode bridge.

OpenCode does not expose a first-class external model-selector plugin surface.
The reliable integration point is the CLI model flag. This wrapper asks Aria for
a route, maps the selected model to an OpenCode model slug, and runs:

    opencode run --model <provider/model> "task"

On Termux, OpenCode's native binary may not run; use --dry-run to inspect the
command. On desktop/Linux hosts with OpenCode installed, this is the practical
Aria model-selector integration.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_ARIA_URL = os.environ.get("ARIA_URL", "http://127.0.0.1:8000").rstrip("/")
DEFAULT_PROVIDER_PREFIX = os.environ.get("ARIA_OPENCODE_PROVIDER_PREFIX", "opencode")
REPO_ROOT = Path(__file__).resolve().parents[1]

# OpenCode installations vary by configured provider. The default assumes the
# user's OpenCode provider is named "opencode" and supports these model slugs.
# Override the prefix with ARIA_OPENCODE_PROVIDER_PREFIX or pass --provider-prefix.
ARIA_TO_OPENCODE_MODEL: dict[str, str] = {
    "kimi-k2.6": "kimi-k2.6",
    "kimi-k2.5": "kimi-k2.5",
    "deepseek-v4-pro": "deepseek-v4-pro",
    "deepseek-v4-flash": "deepseek-v4-flash",
    "MiniMax-M3": "minimax-m3",
    "minimax-m3": "minimax-m3",
    "minimax-m2.7": "minimax-m2.7",
    "minimax-m2.5": "minimax-m2.5",
    "mimo-v2.5": "mimo-v2.5",
    "mimo-v2.5-pro": "mimo-v2.5-pro",
    "glm-5.1": "glm-5.1",
    "glm-5": "glm-5",
    "gpt-5.4-mini": "gpt-5.4-mini",
    "gpt-5.5": "gpt-5.5",
}

BUDGET_TO_MODEL = {
    "cheap": "mimo-v2.5",
    "quality": "kimi-k2.6",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Route an OpenCode task through Aria first")
    parser.add_argument("prompt", nargs="*", help="Task prompt. If omitted, stdin is used.")
    parser.add_argument("--aria-url", default=DEFAULT_ARIA_URL)
    parser.add_argument("--opencode-bin", default=os.environ.get("OPENCODE_BIN", "opencode"))
    parser.add_argument("--provider-prefix", default=DEFAULT_PROVIDER_PREFIX)
    parser.add_argument("--model", help="Bypass Aria and force this OpenCode model")
    parser.add_argument("--budget", choices=["cheap", "balanced", "quality"])
    parser.add_argument("--agent", help="Pass --agent to opencode")
    parser.add_argument("--file", "-f", action="append", default=[], help="Pass file attachments to opencode")
    parser.add_argument("--route-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    task = _task_from_inputs(args.prompt)
    if not task.strip():
        print("aria-opencode: empty task", file=sys.stderr)
        return 2

    route = route_task(task, args.aria_url)
    model = args.model or opencode_model(route, args.provider_prefix, budget=args.budget)

    if args.route_only:
        print(json.dumps({"opencode_model": model, "aria_route": route}, indent=2, ensure_ascii=False))
        return 0

    cmd = [args.opencode_bin, "run", "--model", model]
    if args.agent:
        cmd.extend(["--agent", args.agent])
    for file_path in args.file:
        cmd.extend(["--file", file_path])
    cmd.append(task)

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


def route_task(task: str, aria_url: str) -> dict[str, Any]:
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
            return route
    except Exception as exc:
        return {"source": "unavailable", "error": str(exc), "primary": {"model_id": "kimi-k2.6"}}


def opencode_model(route: dict[str, Any], provider_prefix: str, *, budget: str | None = None) -> str:
    if budget in BUDGET_TO_MODEL:
        slug = BUDGET_TO_MODEL[budget]
    else:
        primary = route.get("primary") or {}
        primary_model = str(primary.get("model_id") or "")
        slug = ARIA_TO_OPENCODE_MODEL.get(primary_model, "kimi-k2.6")
    if "/" in slug:
        return slug
    return f"{provider_prefix}/{slug}" if provider_prefix else slug


if __name__ == "__main__":
    raise SystemExit(main())
