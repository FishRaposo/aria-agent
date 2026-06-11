# Aria model-selector integrations

Aria can sit in front of other coding agents as a **model selector**. The pattern is:

1. A caller sends Aria the task.
2. Aria classifies the task and picks a real model/provider.
3. The integration forwards the task to the target agent with the selected model.

This document covers the three integration surfaces that matter today: Hermes, Command Code, and OpenCode.

## 1. Hermes: model-provider plugin

Aria exposes an OpenAI-compatible facade:

- `GET /v1/models`
- `POST /v1/chat/completions`

The model IDs are virtual routing policies, not concrete upstream models:

- `aria/auto` — route from task text and run the selected model
- `aria/cheap` — force cheap-workhorse routing
- `aria/quality` — force best-quality routing
- `aria/route` — return the routing decision as JSON text, no downstream model call
- `aria/role/<role>` — run a role sub-agent (`planner`, `implementer`, `reviewer`, `researcher`, etc.)

Install the Hermes provider plugin:

```bash
mkdir -p ~/.hermes/plugins/model-providers/aria
cp integrations/hermes_model_provider/aria/__init__.py ~/.hermes/plugins/model-providers/aria/__init__.py
cp integrations/hermes_model_provider/aria/plugin.yaml ~/.hermes/plugins/model-providers/aria/plugin.yaml

# Local Aria does not require auth, but Hermes' API-key provider gate expects a value.
grep -q '^ARIA_API_KEY=' ~/.hermes/.env || echo 'ARIA_API_KEY=local-aria' >> ~/.hermes/.env
grep -q '^ARIA_BASE_URL=' ~/.hermes/.env || echo 'ARIA_BASE_URL=http://127.0.0.1:8000/v1' >> ~/.hermes/.env
```

Start Aria:

```bash
PYTHONPATH="$PWD/src:$HOME/work/operator-shared-core/src" \
  ~/.hermes/hermes-agent/venv/bin/python -m uvicorn aria_agent.main:app \
  --host 127.0.0.1 --port 8000
```

Use from Hermes:

```bash
hermes chat --provider aria -m aria/route -q 'Review this diff for bugs'
hermes chat --provider aria -m aria/auto -q 'Implement a parser regression test'
hermes chat --provider aria -m aria/role/reviewer -q 'Review this PR'
```

Notes:

- Hermes tries streaming first. Aria emits a minimal SSE stream so Hermes does not treat it as provider failure.
- `aria/route` is the safest smoke test because it does not call a downstream model.
- `aria/auto` may call the chosen upstream model and incur cost.

## 2. Command Code: `aria-cmd`

Command Code has no Go-plan provider/plugin API that lets Aria replace its model picker inside a session. The reliable headless integration is a wrapper:

```bash
aria-cmd 'Review this diff for correctness'
git diff | aria-cmd --role reviewer --plan
aria-cmd --budget cheap 'Reply exactly: ok'
```

Flow:

1. `aria-cmd` asks `POST /agent/route` which model should handle the task.
2. It maps Aria model IDs to Command Code IDs:
   - `kimi-k2.6` → `moonshotai/Kimi-K2.6`
   - `MiniMax-M3`/`minimax-m3` → `MiniMaxAI/MiniMax-M3`
   - `mimo-v2.5` → `xiaomi/mimo-v2.5`
3. It executes `cmd --print <task> -m <model>`.

Installed Termux wrapper:

```bash
/data/data/com.termux/files/usr/bin/aria-cmd
```

Dry run / route preview:

```bash
aria-cmd --route-only 'Review this diff for correctness'
aria-cmd --dry-run 'Write a parser regression test'
```

## 3. OpenCode: `aria-opencode`

OpenCode similarly does not expose an external model-selector plugin API. Use the CLI model flag wrapper:

```bash
aria-opencode --dry-run 'Debug failing tests in this repo'
aria-opencode --provider-prefix opencode 'Review this PR'
aria-opencode --budget cheap 'Rename these functions'
```

Flow:

1. `aria-opencode` asks Aria for a route.
2. It maps Aria's chosen model to an OpenCode model slug.
3. It runs `opencode run --model <provider>/<model> <task>`.

Termux caveat: OpenCode's native binary may not run on Android/arm64. The wrapper is still installed and `--dry-run` works; actual execution is for hosts where `opencode run` works.

Installed Termux wrapper:

```bash
/data/data/com.termux/files/usr/bin/aria-opencode
```

## Why not MCP as the primary path?

MCP is good for exposing Aria tools such as `aria_route`, `aria_subagent`, and `aria_orchestrate`, but MCP tools run **inside** an already-started agent session. They cannot reliably choose the top-level model before `cmd --print` or `opencode run` starts.

So the current practical architecture is:

- Hermes: provider plugin (`provider=aria`)
- Command Code: wrapper (`aria-cmd`)
- OpenCode: wrapper (`aria-opencode`)
- Future: optional MCP server for in-session advisory tools
