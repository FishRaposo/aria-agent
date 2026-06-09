# Design Decisions

This document records the key architectural choices made during the development of the Aria Agent (ARIA — Agentic Reasoning & Integration Architecture). Each decision uses ADR (Architecture Decision Record) format.

## Decision 1: Use of Shared Core Utilities

- **Context**: Every project in the showcase portfolio needs boilerplate code for database connections, logging configuration, Redis management, and error handling. Duplicating this across 12 repositories creates maintenance burden and inconsistency.
- **Options**:
  1. Duplicate utilities inside each repository.
  2. Implement a shared `shared-core` library that projects install as an editable package.
  3. Use a monorepo with a single package manager.
- **Choice**: Option 2.
- **Tradeoff**: Single source of truth for config, database, redis, logging, and error modules. Bug fixes propagate instantly to all projects via `pip install -e ../shared-core`. However, every developer must clone `shared-core` alongside the project, and GitHub Actions CI requires special handling for the relative path install.

## Decision 2: Docker Compose for Local Isolation

- **Context**: The agent framework requires PostgreSQL (for future persistence) and Redis (for Celery broker and caching). Developers need reproducible local environments without polluting their host machines.
- **Options**:
  1. Require host-installed PostgreSQL and Redis.
  2. Provide a `docker-compose.yml` with containerized services.
  3. Use SQLite and a mock Redis for development.
- **Choice**: Option 2.
- **Tradeoff**: High reproducibility and zero host dependency pollution. Uses pgvector:pg16 to match production needs (vector storage for future memory embeddings). Costs ~200MB disk for Docker images and requires Docker Desktop, but eliminates "works on my machine" problems.

## Decision 3: Decorator-Based Tool Registry with Pydantic Schemas

- **Context**: Agent frameworks need a way to register tools that the agent can call. The registration mechanism must enforce type safety — if the agent (or an LLM) produces invalid parameters, the system should reject them before execution, not during.
- **Options**:
  1. Free-form dictionary of tool functions with no schema enforcement.
  2. JSON Schema definitions validated at runtime with `jsonschema`.
  3. Pydantic `BaseModel` subclasses paired with a decorator-based registry.
  4. Function signature inspection with `inspect.signature()` for auto-generated schemas.
- **Choice**: Option 3 — `ToolRegistry.register(name, schema)` decorator that stores both the callable and its `type[BaseModel]` schema. `call_tool()` instantiates the schema with provided args (`schema(**args)`) and passes `validated_args.model_dump()` to the function.
- **Tradeoff**: Pydantic v2 gives sub-millisecond validation, rich error messages, and automatic JSON Schema generation (useful for LLM function-calling prompts). The decorator pattern (`@registry.register("name", Schema)`) is idiomatic Python and keeps tool definitions co-located with their implementations. Downside: each tool requires a separate `BaseModel` class, which is more boilerplate than signature inspection — but the explicitness is worth it for safety-critical agent systems where you want to see exactly what parameters a tool accepts.

## Decision 4: Human Approval Gates as a First-Class Concept

- **Context**: In production agent systems, certain tool calls are high-risk (sending emails, creating tasks, modifying files). Allowing an LLM to execute these without human oversight is unacceptable for most enterprise deployments. Many agent frameworks treat approval as an afterthought or plugin — Aria makes it a core architectural concept.
- **Options**:
  1. No approval — trust the agent to make correct decisions.
  2. Global enable/disable flag for all tool calls.
  3. Per-tool permission levels (e.g., `read`, `write`, `destructive`) with configurable approval requirements.
  4. A dedicated `ApprovalGate` class that intercepts every tool call.
- **Choice**: Option 4 for the skeleton, with Option 3 planned for the display-ready milestone. The current `ApprovalGate` class has an `enabled` flag and a `request_approval(action_name, parameters)` method that logs the action and auto-approves. This establishes the architectural seam where real approval logic will be inserted.
- **Tradeoff**: The approval gate adds a synchronous check to every tool call, which introduces latency. For the current auto-approve implementation, this is negligible. For a real async approval queue (planned), the agent run will need to support suspension and resumption — a significant architectural change, but one that the current `request_approval()` interface is designed to accommodate.

## Decision 5: In-Memory Agent Memory (Deferred Persistence)

- **Context**: The agent needs conversation context to produce coherent multi-turn responses. The memory store must track message roles (`user`, `system`, `assistant`) and provide the context window for LLM prompts.
- **Options**:
  1. PostgreSQL-backed memory from day one.
  2. Redis-backed ephemeral memory.
  3. In-memory Python list with persistence added later.
  4. Vector store (pgvector) for semantic memory retrieval.
- **Choice**: Option 3 — `AgentMemory` is a simple class with a `messages: List[Dict[str, str]]` list, `add_message(role, content)`, and `get_context()`.
- **Tradeoff**: Fastest possible iteration for the skeleton phase. No database dependency for the core agent loop to function. The interface (`add_message`, `get_context`) is stable — swapping the backing store to PostgreSQL or Redis requires changing only the implementation, not the callers. Downside: memory is lost on process restart, and there's no sliding-window or token-budget enforcement yet. Both are planned for Phase 2.

## Decision 6: Keyword-Based Tool Selection (MVP Only)

- **Context**: The agent run loop needs to determine which tool to invoke based on the user's message. Production systems use LLM function-calling or ReAct prompting for this, but requiring an LLM API key for the skeleton demo creates a barrier to running the project.
- **Options**:
  1. LLM-based tool selection from day one (requires API keys).
  2. Rule-based / keyword matching as a placeholder.
  3. Embedding similarity between user query and tool descriptions.
- **Choice**: Option 2 — `if "calculate" in user_query.lower()` in `AriaAgent.run()`.
- **Tradeoff**: The demo works without any external API keys, which is critical for a portfolio project that reviewers should be able to run immediately. The keyword matching is clearly a placeholder — it handles exactly one tool and one keyword. The `run()` method is designed to be replaced with LLM-based routing without changing the tool registry, approval gate, or memory interfaces. This intentional separation of concerns is itself a design demonstration.

## Decision 7: Celery for Background Tool Execution

- **Context**: Some tool calls (web searches, file processing, external API calls) may take seconds or minutes. Blocking the FastAPI event loop during these operations degrades the API for all clients.
- **Options**:
  1. Run all tools synchronously in the request handler.
  2. Use `asyncio` tasks within the FastAPI process.
  3. Use Celery with Redis as the broker for true background execution.
  4. Use a custom task queue (like the sibling `async-workflow-engine`).
- **Choice**: Option 3 — `worker.py` configures a Celery app with JSON serialization and UTC timezone.
- **Tradeoff**: Celery is battle-tested and well-understood, with built-in retry logic, result backends, and monitoring (Flower). It's more operational overhead than `asyncio` tasks, but provides process isolation — a crashed tool execution doesn't take down the API. The Redis dependency is already present for caching, so no additional infrastructure is needed. The `async-workflow-engine` (Option 4) will be used for multi-step workflows, while Celery handles individual tool executions.
