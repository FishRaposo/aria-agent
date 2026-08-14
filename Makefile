.PHONY: install dev test lint format typecheck evidence verify-evidence package wheel-check forbidden frontend-install frontend-test frontend-lint frontend-build docker-up docker-down migrate worker demo clean help

install: ## Install ARIA and its declared development tools
	python -m pip install -e ".[dev]"

dev: ## Start the FastAPI development server
	uvicorn aria.main:app --reload --app-dir src --host 0.0.0.0 --port 8000

test: ## Run the offline Python suite
	pytest -q

lint: ## Lint source code with Ruff
	ruff check src/aria tests examples scripts

format: ## Check source formatting with Ruff
	ruff format --check src/aria tests examples scripts

typecheck: ## Static type checking with Pyright
	pyright src/

evidence: ## Generate and verify the deterministic offline portfolio bundle
	python scripts/portfolio_demo.py
	python scripts/verify_portfolio_evidence.py

verify-evidence: ## Verify an existing evidence bundle
	python scripts/verify_portfolio_evidence.py

package: ## Build the wheel and verify its vendored package contents
	python -m build
	python scripts/check_wheel_contents.py

wheel-check: package

forbidden: ## Scan source and operational files for archived dependencies
	python scripts/check_forbidden_dependencies.py

frontend-install: ## Install the dashboard from its lockfile
	cd frontend && npm ci

frontend-test: ## Run dashboard unit tests
	cd frontend && npm test -- --run

frontend-lint: ## Run dashboard lint checks
	cd frontend && npm run lint

frontend-build: ## Build the dashboard for production
	cd frontend && npm run build

docker-up: ## Start optional PostgreSQL and Redis containers
	docker compose up -d

docker-down: ## Stop optional Docker services
	docker compose down

migrate: ## Apply optional database migrations
	alembic upgrade head

demo: ## Run the end-to-end offline agent demo
	python examples/run_demo.py

worker: ## Start the optional Celery worker
	celery -A aria.worker worker --loglevel=info

clean: ## Remove local caches and generated build output
	python -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]; [shutil.rmtree(p, ignore_errors=True) for p in ('dist','build','.pytest_cache','.ruff_cache','.pyright')]"

help: ## Show available commands
	@python -c "import re; from pathlib import Path; [print(f'{m.group(1):18} {m.group(2)}') for m in re.finditer(r'^([a-zA-Z_-]+):.*?## (.*)$$', Path('Makefile').read_text(), re.M)]"
