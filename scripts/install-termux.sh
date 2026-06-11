#!/usr/bin/env bash
# install-termux.sh — Set up aria-agent on Termux, no `pip install` of shared-core.
#
# This script is idempotent. Re-running it just re-verifies the setup.
#
# What it does:
#   1. Verifies Python 3.10+ is available
#   2. Locates the hermes-agent venv (the recommended Python on Termux)
#   3. Locates the operator-shared-core sibling project
#   4. Verifies all required deps are present in the venv
#   5. Verifies imports work via PYTHONPATH (no install)
#   6. Prints a ready-to-use `make demo` command

set -euo pipefail

# ----- Configuration --------------------------------------------------------

ARIA_DIR="${ARIA_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
HERMES_VENV="${HERMES_VENV:-$HERMES_HOME/hermes-agent/venv}"
SHARED_CORE_DIR="${SHARED_CORE_DIR:-$ARIA_DIR/../operator-shared-core}"

# Termux-specific paths
export TMPDIR="${TMPDIR:-/data/data/com.termux/files/usr/tmp}"
mkdir -p "$TMPDIR"

# ----- Pretty output --------------------------------------------------------

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ok()   { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}!${NC} $1"; }
err()  { echo -e "${RED}✗${NC} $1"; }
info() { echo -e "${BLUE}→${NC} $1"; }

# ----- Step 1: Python -------------------------------------------------------

info "Step 1/5: Verifying Python..."

if [ ! -x "$HERMES_VENV/bin/python" ]; then
    err "Hermes-agent venv not found at: $HERMES_VENV"
    err "On Termux, the recommended Python is the hermes-agent venv (it has all the deps)."
    err "If you have a different venv, set HERMES_VENV=/path/to/venv and re-run."
    err "If you want a fresh system install, run: apt install python && pip install pydantic pydantic-settings fastapi openai anthropic loguru httpx"
    exit 1
fi

PYTHON_VERSION=$("$HERMES_VENV/bin/python" --version 2>&1 | awk '{print $2}')
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]; }; then
    err "Python $PYTHON_VERSION found, but 3.10+ is required."
    exit 1
fi

ok "Python $PYTHON_VERSION at $HERMES_VENV/bin/python"

# ----- Step 2: shared-core location ----------------------------------------

info "Step 2/5: Locating operator-shared-core..."

if [ ! -d "$SHARED_CORE_DIR" ]; then
    err "operator-shared-core not found at: $SHARED_CORE_DIR"
    err "aria-agent depends on operator-shared-core (a sibling project)."
    err ""
    err "Either:"
    err "  1. Clone it next to aria-agent:"
    err "     git clone <operator-shared-core-url> $ARIA_DIR/../operator-shared-core"
    err "  2. Or set SHARED_CORE_DIR=/path/to/operator-shared-core and re-run"
    exit 1
fi

if [ ! -d "$SHARED_CORE_DIR/src/shared_core" ]; then
    err "operator-shared-core found at $SHARED_CORE_DIR, but src/shared_core/ is missing."
    err "The repository might be incomplete. Try: cd $SHARED_CORE_DIR && git pull"
    exit 1
fi

SHARED_CORE_VERSION=$(grep -E '^version' "$SHARED_CORE_DIR/pyproject.toml" | head -1 | sed -E 's/.*"([^"]+)".*/\1/')
ok "shared-core $SHARED_CORE_VERSION at $SHARED_CORE_DIR"

# ----- Step 3: Verify deps -------------------------------------------------

info "Step 3/5: Verifying required dependencies in the venv..."

REQUIRED_DEPS=("pydantic" "pydantic_settings" "loguru" "fastapi" "httpx" "openai" "anthropic")
MISSING_DEPS=()

for dep in "${REQUIRED_DEPS[@]}"; do
    if "$HERMES_VENV/bin/python" -c "import $dep" 2>/dev/null; then
        ok "  $dep"
    else
        MISSING_DEPS+=("$dep")
        warn "  $dep (MISSING)"
    fi
done

if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
    err ""
    err "Missing dependencies: ${MISSING_DEPS[*]}"
    err ""
    err "On Termux with the hermes-agent venv, these should already be present."
    err "If they aren't, install them with:"
    err "  $HERMES_VENV/bin/python -m pip install ${MISSING_DEPS[*]}"
    err ""
    err "Note: pip install on Termux is SLOW. If it times out, the live demo"
    err "won't work but tests (which mock the providers) will still pass."
    exit 1
fi

# ----- Step 4: PYTHONPATH import test --------------------------------------

info "Step 4/5: Verifying aria_agent + shared_core import via PYTHONPATH..."

IMPORT_OUTPUT=$(cd "$ARIA_DIR" && PYTHONPATH="$SHARED_CORE_DIR/src:$ARIA_DIR/src" \
    "$HERMES_VENV/bin/python" -c "
import aria_agent
from shared_core.llm import LLMClientFactory
from shared_core.config import BaseAppConfig
print(f'aria_agent {aria_agent.__version__} + shared_core.llm + shared_core.config')
" 2>&1)

if [ $? -eq 0 ]; then
    ok "$IMPORT_OUTPUT"
else
    err "Import test failed:"
    err "$IMPORT_OUTPUT"
    exit 1
fi

# ----- Step 5: Persist a sourced env file -----------------------------------

info "Step 5/5: Writing env helper to $ARIA_DIR/.env.termux..."

cat > "$ARIA_DIR/.env.termux" <<EOF
# Source this file before running aria-agent commands on Termux.
# It sets PYTHONPATH so shared_core is importable without pip install.
#
# Usage:
#   source .env.termux
#   make demo
#   # or directly:
#   PYTHONPATH="\$PYTHONPATH" python examples/run_demo.py

export PYTHONPATH="$SHARED_CORE_DIR/src:$ARIA_DIR/src\${PYTHONPATH:+:\$PYTHONPATH}"
export ARIA_DIR="$ARIA_DIR"
export SHARED_CORE_DIR="$SHARED_CORE_DIR"
export HERMES_VENV="$HERMES_VENV"
EOF

ok "Wrote $ARIA_DIR/.env.termux"

# ----- Done ----------------------------------------------------------------

echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}  aria-agent is ready to use on Termux${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""
echo "Quick start:"
echo ""
echo "  # Run the test suite (no API calls)"
echo "  make test"
echo ""
echo "  # Run the live demo (needs OPENCODE_GO_API_KEY in your env)"
echo "  source \$HOME/.hermes/.env   # loads your OCG API key"
echo "  make demo"
echo ""
echo "  # Or just run a single Python command with the right PYTHONPATH"
echo "  source .env.termux"
echo "  python examples/run_demo.py"
echo ""
echo "  # Start the API server"
echo "  make serve"
echo ""
echo "If you ever see 'No module named shared_core', re-source .env.termux"
echo "or set PYTHONPATH explicitly:"
echo ""
echo "  export PYTHONPATH=\"$SHARED_CORE_DIR/src:$ARIA_DIR/src\""
echo ""
