.PHONY: install dev test lint format typecheck docker-up docker-down demo clean help worker

install: ## Install shared-core and project dependencies
	pip install -e ../shared-core
	pip install -r requirements.txt

dev: ## Start the FastAPI development server
	python src/hermes/main.py

test: ## Run unit tests with pytest
	pytest

lint: ## Lint source code with ruff
	ruff check .

format: ## Auto-format source code with ruff
	ruff format .

typecheck: ## Static type checking with pyright
	pyright src/

docker-up: ## Start PostgreSQL and Redis containers
	docker compose up -d

docker-down: ## Stop all Docker containers
	docker compose down

demo: ## Run the demonstration script
	python examples/run_demo.py

worker: ## Start the Celery worker
	celery -A src.hermes.worker worker --loglevel=info

clean: ## Remove caches and temporary files
	python -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]; shutil.rmtree('.pytest_cache', ignore_errors=True); shutil.rmtree('.ruff_cache', ignore_errors=True)"

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'
