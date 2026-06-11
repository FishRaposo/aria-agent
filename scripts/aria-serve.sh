#!/usr/bin/env bash
# Aria Agent — local FastAPI server
#
# Sourced env (in order): ~/.hermes/.env, then Aria-specific overrides.
# Ensures the uvicorn child sees MINIMAX_API_KEY / OPENCODE_GO_API_KEY /
# OPENAI_CODEX creds so its provider registry can resolve real models.
#
# Usage:
#   aria-serve                # foreground (Ctrl+C to stop)
#   ARIA_HOST=0.0.0.0 aria-serve   # listen on all interfaces
#
# Background: use the Hermes tracked-process API (terminal background=true)
# rather than shell-level nohup/disown wrappers — Hermes can then restart it
# and the user can poll/log it.
set -euo pipefail

ARIA_DIR="${ARIA_DIR:-/data/data/com.termux/files/home/work/aria-agent}"
SHARED_CORE="${SHARED_CORE:-/data/data/com.termux/files/home/work/operator-shared-core}"
HERMES_VENV="${HERMES_VENV:-/data/data/com.termux/files/home/.hermes/hermes-agent/venv}"
HOST="${ARIA_HOST:-127.0.0.1}"
PORT="${ARIA_PORT:-8000}"
LOG="${ARIA_LOG:-/data/data/com.termux/files/usr/tmp/aria-server.log}"

# Sanity-check the three required paths before exec. After `exec` we lose the
# chance to print a useful error message.
for p in "$ARIA_DIR/src" "$SHARED_CORE/src" "$HERMES_VENV/bin/python"; do
  if [ ! -e "$p" ]; then
    echo "aria-serve: required path missing: $p" >&2
    echo "  Set ARIA_DIR / SHARED_CORE / HERMES_VENV env vars to override." >&2
    exit 1
  fi
done

# Ensure the log directory exists (PREFIX/tmp may not on a fresh Termux).
mkdir -p "$(dirname "$LOG")"

# 1. Hermes-level env (API keys, OAuth tokens). Guard the source so a missing
#    file or a syntax error in .env doesn't leave `set -a` toggled on.
if [ -f "$HOME/.hermes/.env" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$HOME/.hermes/.env"
  set +a
fi

# 2. PYTHONPATH so aria_agent + shared_core are importable without pip install.
export PYTHONPATH="$ARIA_DIR/src:$SHARED_CORE/src${PYTHONPATH:+:$PYTHONPATH}"

# 3. `cd` is not strictly required (uvicorn takes an absolute import path)
#    but the Makefile and a few examples assume CWD=$ARIA_DIR.
cd "$ARIA_DIR"

exec "$HERMES_VENV/bin/python" -m uvicorn aria_agent.main:app \
  --host "$HOST" --port "$PORT" --log-level warning \
  >> "$LOG" 2>&1
