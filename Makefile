# Aria Agent — Makefile
# Designed to work on Termux out of the box (no `pip install -e` of shared-core).
# Two execution modes:
#   1. Standard (pip install -e .  +  pip install -e ../operator-shared-core)
#   2. Termux-friendly (PYTHONPATH only, no install — uses hermes-agent venv)
# Set TERMUX=1 to force mode 2. Default: auto-detect (mode 2 if hermes-agent venv exists).

# ----- Configuration --------------------------------------------------------

# Auto-detect Termux mode: on if hermes-agent venv is present at the canonical path.
HERMES_VENV ?= $(HOME)/.hermes/hermes-agent/venv
ifneq ($(wildcard $(HERMES_VENV)/bin/python),)
  TERMUX_MODE := 1
else
  TERMUX_MODE := 0
endif

# Sibling project that aria-agent depends on
SHARED_CORE_DIR ?= $(CURDIR)/../operator-shared-core

# Python interpreter
ifeq ($(TERMUX_MODE),1)
  PYTHON := $(HERMES_VENV)/bin/python
else
  PYTHON := python3
endif

# PYTHONPATH for Termux mode (no install needed)
ifeq ($(TERMUX_MODE),1)
  PYTHONPATH := $(SHARED_CORE_DIR)/src:$(CURDIR)/src
  export PYTHONPATH
endif

# ----- Targets --------------------------------------------------------------

.PHONY: help install install-termux test demo serve lint format typecheck clean verify

help: ## Show this help
	@echo "Aria Agent — Makefile"
	@echo ""
	@echo "Mode: $(if $(filter $(TERMUX_MODE),1),TERMUX (PYTHONPATH, no install),STANDARD (pip install -e))"
	@echo "Python: $(PYTHON)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

verify: ## Verify imports work (no install, no API calls)
	@echo "Mode: $(if $(filter $(TERMUX_MODE),1),TERMUX,STANDARD)"
	@echo "Python: $(PYTHON)"
	@$(PYTHON) -c "import sys; sys.path.insert(0, '$(SHARED_CORE_DIR)/src'); sys.path.insert(0, 'src'); import aria_agent; from shared_core.llm import LLMClientFactory; print('OK — aria_agent', aria_agent.__version__, '+ shared_core.llm')"

install: ## Standard install (pip install -e . + shared-core sibling)
	@echo "Installing aria-agent and shared-core (sibling)..."
	$(PYTHON) -m pip install -e $(SHARED_CORE_DIR)
	$(PYTHON) -m pip install -e .

install-termux: ## Termux-friendly install (uses hermes-agent venv, PYTHONPATH)
	@echo "Verifying Termux setup..."
	@bash scripts/install-termux.sh

test: ## Run unit tests
	$(PYTHON) -m pytest tests/

demo: ## Run the live demo (uses OPENCODE_GO_API_KEY)
	$(PYTHON) examples/run_demo.py

serve: ## Start the FastAPI gateway (uvicorn)
	$(PYTHON) -m uvicorn aria_agent.main:app --host 0.0.0.0 --port 8000

lint: ## Lint with ruff
	$(PYTHON) -m ruff check .

format: ## Auto-format with ruff
	$(PYTHON) -m ruff format .

typecheck: ## Static type checking with pyright
	$(PYTHON) -m pyright src/

clean: ## Remove caches
	$(PYTHON) -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]; shutil.rmtree('.pytest_cache', ignore_errors=True); shutil.rmtree('.ruff_cache', ignore_errors=True)"
