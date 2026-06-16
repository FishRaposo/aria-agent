.PHONY: install dev test lint format typecheck docker-up docker-down demo migrate worker clean help

install: ## Install shared-core and project dependencies
	pip install -e "../shared-core[dev,docparse]" numpy
	pip install -e ".[dev]"

dev: ## Start the FastAPI development server
	uvicorn hermes.main:app --reload --app-dir src --host 0.0.0.0 --port 8000

test: ## Run the test suite with pytest
	pytest -q

lint: ## Lint source code with ruff
	ruff check src/hermes tests examples

format: ## Auto-format source code with ruff
	ruff format src/hermes tests examples

typecheck: ## Static type checking with pyright
	pyright src/

docker-up: ## Start PostgreSQL and Redis containers
	docker compose up -d

docker-down: ## Stop all Docker containers
	docker compose down

migrate: ## Apply database migrations (optional — DB is not required)
	alembic upgrade head

demo: ## Run the end-to-end agent demo
	python examples/run_demo.py

worker: ## Start the Celery worker
	celery -A hermes.worker worker --loglevel=info

clean: ## Remove caches and temporary files
	python -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]; shutil.rmtree('.pytest_cache', ignore_errors=True); shutil.rmtree('.ruff_cache', ignore_errors=True)"

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'
