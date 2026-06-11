# Termux Compatibility

Aria Agent is designed to run on Termux (Android/arm64) as a first-class host — that's the
machine this project is actively developed on. The constraints are real, the workarounds
are explicit, and the regression guard lives in `tests/test_termux_compat.py` (25 tests,
must stay green on every change).

## Why Termux is special

- **No system `pip` you can rely on.** `apt install python` works, but `pip install` of
  many scientific packages fails (build toolchain missing or too old, or the wheel is
  arm64-linux-android and pip can't find it).
- **No `pip install -e` for the dev workflow.** Symlink installs are fine, but the
  recommended pattern is `PYTHONPATH`-only — Aria and `operator-shared-core` are both
  loaded as source, no install step.
- **`/tmp` is read-only.** Tools that write to `/tmp` (many do, by default) will fail
  with `OSError: [Errno 30] Read-only file system`. Use `$PREFIX/tmp` (typically
  `/data/data/com.termux/files/usr/tmp`) instead.
- **CGO binaries often don't work.** The musl-cross toolchain Termux ships with has a
  `libstdc++` built by GCC 11.2.1; some upstream binaries need a newer C++ runtime and
  refuse to load. This blocks OpenCode, some `whisper.cpp` builds, full `sharp` (the
  Node image lib), and several `ctranslate2` wheels.
- **Hermes-agent venv is the recommended Python.** It has all the Aria deps already
  installed (`pydantic`, `fastapi`, `loguru`, `openai`, `httpx`, `anthropic`, etc.).
  System Python is fine for the calculator, but anything that touches providers needs
  the venv.

## The 4 things that have to be true for Aria to run on Termux

| # | Invariant | Where it's enforced |
|---|---|---|
| 1 | `aria_agent` and `shared_core` are importable via `PYTHONPATH` (no `pip install`) | `scripts/aria-serve.sh`, `scripts/install-termux.sh`, `.env.termux` |
| 2 | API keys reach the uvicorn child (Hermes `.env` must be sourced before exec) | `scripts/aria-serve.sh` |
| 3 | The CLI wrappers (`aria-cmd`, `aria-opencode`) can reach Aria at `http://127.0.0.1:8000` | `ARIA_BASE_URL` in `~/.hermes/.env` |
| 4 | Logs go to `$PREFIX/tmp`, not `/tmp` | `scripts/aria-serve.sh` defaults `LOG` to `$PREFIX/tmp/aria-server.log` |

`tests/test_termux_compat.py` covers 25 invariants in 5 classes:

1. **Full import surface** — every public symbol Aria exposes imports cleanly.
2. **`resolve_decision` graceful fallback** — when the routing table's preferred
   model is on an unregistered provider, the registry walks the fallback chain
   (primary → fallback → escalation → table default → any registered model) instead
   of raising `KeyError`. Critical for the $1/mo Go plan where only OCG is callable.
3. **All active sub-agent roles resolve to a callable model** — every
   `SubAgentRole.{PLANNER, ARCHITECT, IMPLEMENTER, DEBUGGER, DOCUMENTER, REVIEWER,
   TESTER, VALIDATOR, RESEARCHER}` produces a `(provider, model)` pair that the
   registry can actually call. Tested in three provider configurations: full
   (OCG + MiniMax + Codex), bare OCG, and no-keys.
4. **Calculator safety** — the v0.4 calculator replaced `eval()` with an AST
   walker. Hostile inputs (function calls, attribute access, file I/O, booleans
   as int, string literals, comparisons, assignments) all return friendly
   errors instead of executing.
5. **Termux invariants** — `$PREFIX/tmp` is writable; hermes venv python runs.

## How to set up Aria on a fresh Termux

```bash
# 1. Install Hermes Agent (separate project; gives you the venv + .env)
#    See hermes-agent docs for the install.

# 2. Clone Aria + the shared-core sibling
git clone <aria-agent-url> ~/work/aria-agent
git clone <operator-shared-core-url> ~/work/operator-shared-core

# 3. Run the idempotent Termux installer
bash ~/work/aria-agent/scripts/install-termux.sh
# It writes .env.termux with the right PYTHONPATH; source it before any Aria work.

# 4. Start Aria (sources ~/.hermes/.env, sets PYTHONPATH, writes to $PREFIX/tmp)
~/work/aria-agent/scripts/aria-serve.sh &
# Verify:
curl http://127.0.0.1:8000/health
# {"status":"healthy","providers_configured":2,...}
```

If `providers_configured: 0` shows up, the wrapper didn't source `.env` — check
that `~/.hermes/.env` exists and contains at least one of `OPENCODE_GO_API_KEY`,
`MINIMAX_API_KEY`, or `OPENAI_CODEX`.

## Patterns that work

### Starting the Aria server

**Always** use `scripts/aria-serve.sh`. Don't use `make serve` or raw `uvicorn` —
they don't source `.env`, so the uvicorn process has no provider keys and reports
`providers_configured: 0`.

```bash
# Foreground (good for one-shots)
~/work/aria-agent/scripts/aria-serve.sh

# Background via the Hermes tracked-process API (recommended for long-running)
#   terminal(background=true) with command = the wrapper path
```

The wrapper does five things, in order:
1. Sanity-checks `$ARIA_DIR/src`, `$SHARED_CORE/src`, `$HERMES_VENV/bin/python` exist
   (so a clear error appears before `exec`, instead of a cryptic uvicorn crash).
2. Sources `~/.hermes/.env` with `set -a` / `set +a` so all keys auto-export.
3. Sets `PYTHONPATH="$ARIA_DIR/src:$SHARED_CORE/src:..."`.
4. `cd "$ARIA_DIR"` (the demo and Makefile assume CWD = Aria root).
5. `exec` uvicorn with stdout/stderr to `$LOG` (default `$PREFIX/tmp/aria-server.log`).

### Using the CLI bridges

```bash
# Command Code bridge — ask Aria for a route, then run cmd --print with that model
aria-cmd --route-only "Review this diff for correctness"
aria-cmd --budget cheap --max-turns 1 "Reply exactly: ok"

# OpenCode bridge — same idea, dry-run on Termux (native binary not available)
aria-opencode --dry-run "Debug failing tests in this repo"
```

Both wrappers are installed at `$PREFIX/bin/aria-cmd` and `$PREFIX/bin/aria-opencode`
and source their logic from `~/work/aria-agent/integrations/`.

### Background processes via the Hermes tracked-process API

The Hermes `terminal(background=true)` mode is the only correct way to spawn a
long-lived process from inside a tool call. Shell-level `nohup` / `disown` /
`setsid` / trailing `&` are blocked because they bypass Hermes' lifecycle
tracking — the user would have no way to know the process died or to see its
log.

```bash
# CORRECT: use Hermes' tracked background mode (not blocked)
terminal(background=true, command="/path/to/aria-serve.sh")
# Then poll/wait/log via the `process` tool.

# WRONG: foreground command that uses &, nohup, or disown
nohup /path/to/aria-serve.sh &
```

The `aria-serve.sh` wrapper writes its own log to `$PREFIX/tmp/aria-server.log`,
so you can `tail -f` it for debugging without touching Hermes' process state.

## What does NOT work on Termux (and why)

| Feature | Status | Why |
|---|---|---|
| **OpenCode native CLI** | ❌ blocked | CGO binary, musl-cross toolchain libstdc++ is GCC 11.2.1, too old for OpenCode's compiled objects. |
| **Full `sharp` (Node image lib)** | ❌ blocked | Needs a newer libstdc++. Workaround: `npm i --force @img/sharp-wasm32 sharp` for the wasm32 fallback. |
| **Local `whisper.cpp` / `ctranslate2`** | ❌ blocked | No prebuilt wheels; build fails in the Termux cross toolchain. Use Groq Whisper or OpenAI Whisper instead. |
| **Matrix E2EE (`python-olm`)** | ❌ blocked | `python-olm` fails to build on Termux. Plain-text Matrix is fine. |
| **`make serve` (raw)** | ❌ no env | Sources nothing. Always use `scripts/aria-serve.sh` instead. |
| **CGO from any project** | ⚠️ risky | Toolchain-dependent. If the binary doesn't load, look for a pure-Go or pure-Python alternative. |
| **Long-running processes via shell `&`** | ❌ blocked by Hermes | Use `terminal(background=true)` instead. |

## Aria as a Hermes provider

Aria exposes an OpenAI-compatible `/v1/chat/completions` endpoint and a
`/v1/models` catalog. Install the Hermes provider plugin so Hermes can route
to Aria by `provider=aria, model=aria/<virtual>`:

```bash
mkdir -p ~/.hermes/plugins/model-providers/aria
cp ~/work/aria-agent/integrations/hermes_model_provider/aria/{__init__.py,plugin.yaml} \
   ~/.hermes/plugins/model-providers/aria/
grep -q '^ARIA_API_KEY=' ~/.hermes/.env || echo 'ARIA_API_KEY=local-aria' >> ~/.hermes/.env
grep -q '^ARIA_BASE_URL=' ~/.hermes/.env || echo 'ARIA_BASE_URL=http://127.0.0.1:8000/v1' >> ~/.hermes/.env
```

Virtual model IDs:
- `aria/auto` — route from task text and run the chosen model
- `aria/cheap` — force cheap workhorse
- `aria/quality` — force best quality
- `aria/route` — return routing decision as JSON text (no model call)
- `aria/role/<planner|implementer|reviewer|researcher|...>` — run a sub-agent

Hermes tries streaming first. Aria emits a minimal SSE stream
(`data: {chunk}…\n\ndata: {done}…\n\ndata: [DONE]\n\n`) so Hermes doesn't
treat Aria as a failed provider on the streaming path.

## The watchdog pattern

`~/.hermes/scripts/gateway_health_check.py` runs every 5 minutes via cron and
silently (or noisily, on failure) verifies that the gateway is up. It uses
`pgrep -af "venv/bin/hermes gateway"` and requires the cmdline to END with
`"gateway"` (real gateway) instead of the literal `" gateway run"` (which
would never match — there is no `run` subcommand). A real gateway line:

```
11977 .../venv/bin/python .../venv/bin/hermes gateway
```

A wrapper-shell line that happens to contain the pattern:

```
12728 bash -c ... pgrep -af 'venv/bin/hermes gateway' ...
```

The "ends with gateway" filter is the differentiator.

## See also

- `scripts/install-termux.sh` — idempotent install/verify
- `scripts/aria-serve.sh` — the only correct way to start Aria on Termux
- `tests/test_termux_compat.py` — 25-test regression guard
- `docs/integrations-model-selector.md` — the three CLI bridges
- `~/.hermes/skills/software-development/aria-subagents/SKILL.md` — v1.2.0
  skill for the Hermes-side invocation patterns
