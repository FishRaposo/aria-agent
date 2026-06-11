#!/data/data/com.termux/files/usr/bin/bash
# Aria Agent — local FastAPI server
#
# Sourced env (in order): ~/.hermes/.env, then Aria-specific overrides.
# Ensures the uvicorn child sees MINIMAX_API_KEY / OPENCODE_GO_API_KEY /
# OPENAI_CODEX creds so its provider registry can resolve real models.
#
# Usage:
#   aria-serve            # foreground (kill with Ctrl+C)
#   aria-serve --bg       # background via Hermes tracked-process API
set -e

ARIA_DIR="/data/data/com.termux/files/home/work/aria-agent"
SHARED_CORE="/data/data/com.termux/files/home/work/operator-shared-core"
HERMES_VENV="/data/data/com.termux/files/home/.hermes/hermes-agent/venv"
HOST="${ARIA_HOST:-127.0.0.1}"
PORT="${ARIA_PORT:-8000}"
LOG="${ARIA_LOG:-/data/data/com.termux/files/usr/tmp/aria-server.log}"

# 1. Hermes-level env (API keys, OAuth tokens)
[ -f "$HOME/.hermes/.env" ] && set -a && . "$HOME/.hermes/.env" && set +a

# 2. PYTHONPATH so aria_agent + shared_core are importable
export PYTHONPATH="$ARIA_DIR/src:$SHARED_CORE/src${PYTHONPATH:+:$PYTHONPATH}"

cd "$ARIA_DIR"
exec "$HERMES_VENV/bin/python" -m uvicorn aria_agent.main:app \
  --host "$HOST" --port "$PORT" --log-level warning \
  >> "$LOG" 2>&1
