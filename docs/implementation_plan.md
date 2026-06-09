# Implementation Plan - Aria Agent

This document details the step-by-step technical implementation plan and development milestones for **Aria Agent**.

---

## 1. Project Goal
A lightweight agent framework providing tool-calling models, stateful memory stores, and human-in-the-loop approval gates for secure agentic executions.

---

## 2. Architecture & Component Map

The repository is structured as a standalone project conforming to operator workspace standards. The core module responsibilities are mapped below:

### 2.1 File Map & Responsibilities
* **`src/aria_agent/agent.py`**: Core run-loop implementing step-by-step reasoning, tool invocations, and termination checks.
* **`src/aria_agent/tools.py`**: Tool registration manager verifying parameters schema via Pydantic model configurations.
* **`src/aria_agent/memory.py`**: Stateful conversation memory storage and vector-backed semantic retrieval database.
* **`src/aria_agent/approvals.py`**: Human-in-the-loop permission gateway intercepting sensitive tools (e.g. database deletes, git pushes).

### 2.2 Shared Core Dependencies
This service imports standard layers from `shared-core` (sibling dependency library):
* `shared_core.config.BaseAppConfig`: Settings parsing, reading configs from `.env`.
* `shared_core.database.DatabaseManager`: SQL database engine instantiation and session factories.
* `shared_core.redis.RedisManager`: Caching connections and health checks.
* `shared_core.logging.setup_logging`: Structured log formats and correlation ID tracing.
* `shared_core.errors.BaseApplicationError`: Exception mapping and global handlers.

---

## 3. Database Schema & Data Models

### 3.1 Data Schema
PostgreSQL: `agent_sessions` (id, created_at, status), `agent_steps` (id, session_id, step_index, thought, action_name, action_input, response, cost, latency_ms), `approval_queue` (id, step_id, status, requested_at, reviewed_at).
Redis: Active session storage and memory locking.

### 3.2 Redis Storage & Caching Patterns
* Caching: Utilizing `@cache` decorator with prefix keys.
* Concurrency: Lock critical tasks using `RedisLock` context managers.

---

## 4. Step-by-Step Implementation Sequence

The project development checklist is ordered into six milestones:

- `[ ]` **Milestone 1 (Design): Design tool-calling JSON loop and approval interceptor pattern.**
- `[ ]` **Milestone 2 (Skeleton): Write basic Pydantic tool schemas and FastAPI session endpoints.**
- `[ ]` **Milestone 3 (Core Loop): Implement agent reasoning step execution loop with tool call executions.**
- `[ ]` **Milestone 4 (Reliability): Add sandbox execution rules, system role prompts, and prompt injection bounds.**
- `[ ]` **Milestone 5 (Showcase): Build demo CLI agent calling web search and file writing tools with human gates.**
- `[ ]` **Milestone 6 (Publish): Document tool registration, approval configurations, and memory layout.**

---

## 5. Standard Makefile & Developer Commands

```bash
make install          # Set up virtual environment and local editable package
make dev              # Boot the microservice API server locally
make test             # Run local pytest / jest test suites
make lint             # Execute Ruff checks / ESLint verifications
make format           # Standardize style formatting
make typecheck        # Verify static types (Pyright / TypeScript)
make docker-up        # Spawn isolated local PostgreSQL and Redis service containers
make docker-down      # Teardown the isolated local containers stack
make demo             # Execute the runnable demo workflow
make clean            # Remove caches and temporary files
```

---

## 6. Verification & Testing Plan

### 6.1 Automated Tests
* **Core Logic Verification**: Tests for tool schema validation, loop termination, mock tool execution, and approval gate blocks.
* **Type Safety & Style**: Run `make typecheck` and `make lint` as a pipeline validation hook.
* **Mock Environments**: Utilize `MockDatabase` and `MockRedisClient` inside `tests/conftest.py` to assert correct lifecycle transactions without depending on live network services.

### 6.2 Manual Verification
* Deploy local PostgreSQL and Redis containers with `make docker-up`.
* Execute the runnable script demo `make demo` and review Loguru stdout records.
