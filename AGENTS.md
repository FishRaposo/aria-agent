# Aria Agent — Agent Guide for LLMs

This file is for future agents (LLMs or otherwise) working on this codebase. It's intentionally not auto-generated — keep it accurate as the project evolves.

## What this project is

A **cross-provider model router with cooperation patterns, a v0.1 tool agent, and v0.4 sub-agents**. v0.4 unifies three execution paths into a single orchestrator:

- **Tool path (v0.1, preserved):** `KeywordRouterAgent` does keyword-based tool dispatch on the 5 builtin tools (calculator, web_search, file_reader, task_creator, email_draft). Fast, deterministic, no LLM cost.
- **Model path (v0.2, preserved):** `ModelSelector` picks the best (provider, model) pair for a task; `CooperationPattern` orchestrates multiple models (cascade, plan-execute-validate, ensemble) when a task benefits.
- **Sub-agent path (v0.4, new):** `Orchestrator` runs multiple `SubAgent`s (planner, architect, implementer, debugger, documenter, reviewer, tester, validator, researcher) in **parallel** (independent perspectives) or **sequential** (chained with context). Each role has a model picked specifically for that kind of work.

`AriaAgent` is the entry point for tool + model paths. `Orchestrator` is the entry point for sub-agent paths. They share the same `ProviderRegistry` and `ModelSelector`.

**Stack:** Python 3.10+, FastAPI, Pydantic, async, depends on `operator-shared-core` (a sibling project).

**Phase:** v0.4 (active). Builds on v0.1 (tools) + v0.2 (router/cooperation) + v0.3 (unified orchestrator) — see "What v0.4 adds" below.

**Termux:** Designed to run on Termux out of the box. `bash scripts/install-termux.sh` does the whole setup (no `pip install -e`). The Makefile auto-detects Termux mode and uses PYTHONPATH only. **Start the server with `scripts/aria-serve.sh`, not `make serve` — the wrapper sources `~/.hermes/.env` so the uvicorn child sees the API keys.** See `docs/termux-compat.md` for the full strategy and the 25-test regression guard in `tests/test_termux_compat.py`.

## What v0.4 adds (vs. v0.3)

- **`SubAgentRole` enum** — 9 specialist roles (planner, architect, implementer, debugger, documenter, reviewer, tester, validator, researcher). Each gets a model picked for that kind of work via `ModelInfo.role_preferences` in the routing table.
- **Role-based routing** — `ModelSelector.select_for_role(role)` picks the best model for a role. Data-driven: each `ModelInfo` declares which roles it claims.
- **`SubAgent` class** — single-role worker. Picks model via the role router, makes one LLM call, returns structured `SubAgentResult` (model used, output, cost, latency, success).
- **`SubAgentRegistry`** — role → SubAgent catalog. Defaults to one sub-agent per role; users can register custom specs (different system prompt, temperature, max_tokens) or pin a specific model.
- **`Orchestrator`** — runs multiple sub-agents in parallel (asyncio.gather) or sequential (chain with prior output as context). Two-level patterns are composable (e.g., parallel {planner, architect} → sequential {implementer, validator}).
- **HTTP API** — new endpoints:
  - `GET /subagents` — list all roles + their default model picks
  - `POST /subagent/run` — run a single sub-agent
  - `POST /orchestrator/run` — run multiple sub-agents (parallel or sequential)
- **Hermes integration** — `aria-agent/integrations/hermes_aria_tool.py` — drop-in tool file that lets Hermes invoke Aria sub-agents via HTTP.
- **Command Code integration** — `aria-subagents` skill at `~/.hermes/skills/software-development/aria-subagents/SKILL.md` — full skill documentation for invoking Aria from CMD's agent loop.

## Sub-agent role → model mapping

| Role | Default model | Why |
|---|---|---|
| planner | kimi-k2.6 (best_quality, TB 54.4%) | Best for deep reasoning, multi-step planning |
| architect | kimi-k2.6 | Broad design thinking |
| implementer | MiniMax-M3 (default) | Native coding, multimodal |
| debugger | deepseek-v4-pro (long_context) | Hybrid attention, logical analysis |
| documenter | kimi-k2.6 | Best quality, writing |
| reviewer | glm-5.1 (best_quality) | Multi-mode thinking, code review |
| tester | MiniMax-M3 | Default, edge-case generation |
| validator | glm-5.1 | Multi-mode, correctness checks |
| researcher | deepseek-v4-pro | Long context, synthesis |

Override any role's model per-call via `model_id` parameter, or override the whole budget via `budget="cheap"` (force mimo-v2.5) / `budget="quality"` (force highest TB).

## Quick orientation

- **Three paths, one orchestrator**: `AriaAgent` is the tool+model entry point. `Orchestrator` is the sub-agent entry point. They share `ProviderRegistry` and `ModelSelector`.
- **The provider layer** at `src/aria_agent/providers/`. OCG handles 2 protocols (chat-completions for Kimi/MiniMax/mimo/Qwen 3.6, Anthropic Messages for Qwen 3.7). The router doesn't know about this — it just says "use kimi-k2.6", the provider figures out the protocol.
- **Per-request state.** The agent + registry + sub_agent_registry are constructed once at app startup, shared across requests. Per-request state (memory, trace, cost) is created inside `_run_tool_path` for the tool path. Sub-agents are stateless; the orchestrator creates per-request context.
- **The v0.1 `KeywordRouterAgent` is a specialist** that the new `AriaAgent` delegates to. It is NOT the main entry point — `AriaAgent` is.
- **The demo** (`examples/run_demo.py`) is the source of truth for "what does this look like end-to-end?" It demos both paths (3 model tasks + 3 tool tasks).

## Source modules

| Path | Purpose | When to update |
|---|---|---|
| `scripts/install-termux.sh` | Termux setup (idempotent) | New dep added; new install mode |
| `scripts/aria-serve.sh` | Start the Aria server on Termux (sources .env, sets PYTHONPATH, logs to $PREFIX/tmp) | Server start path or log location changes |
| `Makefile` | Auto-detects Termux (uses hermes-agent venv) vs standard | New target added; new env override |
| `integrations/hermes_aria_tool.py` | Drop-in Hermes tool for Aria sub-agents | New sub-agent role added; new HTTP endpoint |
| `src/aria_agent/__init__.py` | Public API exports (v0.1 + v0.2 + v0.3 + v0.4) | New top-level symbol added |
| `src/aria_agent/agent.py` | `AriaAgent` orchestrator (v0.3) | New intent rule; new path |
| `src/aria_agent/agents.py` | `KeywordRouterAgent` (v0.1) + alias | v0.1 keyword logic changes |
| `src/aria_agent/approvals.py` | `ApprovalGate` (v0.1) | Approval policy changes |
| `src/aria_agent/memory.py` | `AgentMemory` (v0.1) | Storage backend changes |
| `src/aria_agent/costs.py` | `CostTracker` (v0.1) | Cost calc source changes |
| `src/aria_agent/tracing.py` | `TraceLog` (v0.1) | Trace format changes |
| `src/aria_agent/worker.py` | Celery worker (v0.1) | Async run changes |
| `src/aria_agent/tools.py` | `ToolRegistry` (v0.1) | Tool registration changes |
| `src/aria_agent/builtin_tools/` | 5 v0.1 tools (calculator, web_search, file_reader, task_creator, email_draft) | Tool implementation changes |
| `src/aria_agent/main.py` | FastAPI gateway (v0.4) | New endpoint; per-request state changes |
| `src/aria_agent/config.py` | `AppConfig` (Pydantic settings) | New env var or config knob |
| `src/aria_agent/providers/base.py` | Abstract `BaseProvider` + `ProviderError` | Provider contract changes |
| `src/aria_agent/providers/openai_compatible.py` | Base for OpenAI-style providers | OpenAI protocol changes |
| `src/aria_agent/providers/minimax.py` | MiniMax direct | MiniMax API/protocol changes |
| `src/aria_agent/providers/opencode_go.py` | OCG (handles split routing) | OCG protocol split changes |
| `src/aria_agent/providers/openai_codex.py` | OpenAI Codex (OAuth) | Codex auth flow changes |
| `src/aria_agent/providers/registry.py` | Provider/model registry | New provider; lazy construction rules |
| `src/aria_agent/router/routing_table.py` | Catalog of routable models + role_preferences | New model; cost/TB/role changes |
| `src/aria_agent/router/classifier.py` | Task → TaskType | New keyword or task type added |
| `src/aria_agent/router/selector.py` | TaskType → (primary, fallback, escalation); Role → (primary, fallback, escalation) | Budget override rules; tier ordering; role routing changes |
| `src/aria_agent/cooperation/base.py` | `CooperationPattern` ABC + `assess_quality` | New quality metric; new step type |
| `src/aria_agent/cooperation/cascade.py` | Cascade/escalation pattern | Cascade strategy changes |
| `src/aria_agent/cooperation/plan_execute.py` | Plan-execute-validate pattern | Pipeline prompt changes |
| `src/aria_agent/cooperation/ensemble.py` | Parallel ensemble + pick-best | Combiner logic changes |
| `src/aria_agent/cooperation/__init__.py` | Public exports for cooperation | New pattern added |
| `src/aria_agent/subagents/__init__.py` | Public exports for sub-agents | New sub-agent type added |
| `src/aria_agent/subagents/base.py` | `SubAgent`, `SubAgentResult`, `SubAgentRoleSpec`, `DEFAULT_ROLE_SPECS`, `SYSTEM_PROMPTS` | New role; new system prompt; role routing change |
| `src/aria_agent/subagents/registry.py` | `SubAgentRegistry` | New registration pattern |
| `src/aria_agent/subagents/orchestrator.py` | `Orchestrator`, `OrchestrationResult`, `OrchestrationStep` | New orchestration pattern |

## When to update

- **Tool keyword changed** → update `_TOOL_KEYWORDS` in `agent.py` AND `_plan_action` in `agents.py`. They must stay in sync.
- **New tool added** → add to `builtin_tools/`, register in `main.py`, add keywords to both keyword tables. Tests in `test_tools.py` and `test_agent.py`.
- **Routing rules change** (new model, new pricing, new TB score) → update `router/routing_table.py`. Consider running `examples/run_demo.py` to verify.
- **Role preferences changed** (a model should claim a new role, or stop claiming one) → update `ModelInfo.role_preferences` in `routing_table.py`. Tests in `test_subagents.py` will catch the changes.
- **New sub-agent role added** → add to `SubAgentRole` enum, add system prompt to `SYSTEM_PROMPTS`, add default spec to `DEFAULT_ROLE_SPECS`. Update `ModelInfo.role_preferences` for any model that should claim the new role. Tests in `test_subagents.py`.
- **New cooperation pattern** → create a new file in `cooperation/`, register in `cooperation/__init__.py` and `agent.py:_PATTERN_REGISTRY`. Add tests in `tests/test_cooperation.py`.
- **OCG adds a new model with a new protocol** → update `providers/opencode_go.py:OPENCODE_GO_MODELS` (the protocol map). The router will pick it up automatically.
- **Tests fail in CI** → check if the model list changed (OCG rotated) or if the API contract shifted. Re-run `examples/run_demo.py` to see live behavior.

## Patterns / invariants

- **Three execution paths, two entry points.** `AriaAgent.run()` returns a `CooperationResult` (tool or model path). `Orchestrator.run_parallel()` / `run_sequential()` returns an `OrchestrationResult` (sub-agent path). They share the same provider registry and router.
- **Role-based model pick is data-driven.** Each `ModelInfo` declares which `SubAgentRole`s it claims via `role_preferences`. The router queries this. To change which model a role uses, update the routing table — don't add special-case code in the selector.
- **Sub-agents are stateless.** The registry holds role→SubAgent mappings. Each `sub_agent.run(task)` is a single LLM call returning a `SubAgentResult`. The orchestrator creates per-request context (sequential mode passes prior output as `context`).
- **Per-request state.** No module-level mutable dicts/lists. The `main.py` constructs `agent`, `registry`, `router`, `sub_agent_registry`, and `orchestrator` once at startup; the FastAPI app reuses them across requests.
- **Provider is lazy.** `ProviderRegistry` constructs a provider only when its key is set. Don't change this — it lets the agent run with partial key configuration.
- **Tool keywords must be in sync.** `_TOOL_KEYWORDS` in `agent.py` and `_plan_action` in `agents.py` cover the same set of tools.
- **Cooperation patterns return `CooperationResult`**, not raw strings. The agent and gateway are designed around this.
- **Orchestrator returns `OrchestrationResult`**, not raw strings. The sub-agent system has its own result type, separate from the cooperation result type.
- **OCG split routing is encoded in the provider, not the router.** The router says "use kimi-k2.6", the provider figures out the protocol.
- **Calculator special case.** "calculate" with no digits → model path, not tool path.

## Known limitations (intentional, deferred)

- **Rule-based intent classifier (v1).** Works for common cases. LLM-based classifier on the roadmap.
- **Sub-agents have no tools.** Each sub-agent is a single LLM call. For tool use, use the v0.3 AriaAgent orchestrator instead.
- **Sub-agents don't see each other's outputs in parallel mode.** By design — they're independent. Use sequential mode for cross-pollination.
- **Length-based ensemble combiner (v1).** Doesn't measure semantic quality. Model-as-judge on roadmap.
- **No persistent state.** Each request is independent. No DB, no Redis, no Celery dispatch. Add when needed.
- **v0.1 calculator uses `eval()`** — sandboxed with no builtins, but still `eval`. Replace with a real math parser when convenient.
- **Auto-approve everything.** No real approval gate. v0.1's `ApprovalGate` always returns True.
- **OpenAI Codex not tested live.** Provider implemented but user's plan (Go) doesn't include Pro+ gated models.

## Test conventions

- Tests use `FakeProvider` and `FakeRegistry` (defined in `tests/test_cooperation.py` and reused). Mock the provider layer; the routing and cooperation logic is the unit under test.
- Provider tests are wiring tests (model lists, registry construction, resolve_model). Not live API tests.
- The live demo (`examples/run_demo.py`) is the manual integration test. Run it after any change to the routing table or OCG provider. It demos both paths.
- `tests/test_agent.py` includes gateway tests that **skip if loguru is missing** (a shared-core dep). When the env is fully provisioned, those tests run.
- `tests/test_agents.py` covers the v0.1 `KeywordRouterAgent` (preserved). The class was renamed in v0.3; the old name `AriaAgent` is an alias.
- `tests/test_agent.py` has `TestAriaAgentV3Integration` for v0.3 orchestrator behavior.
- `tests/test_subagents.py` covers v0.4 sub-agents: role routing, SubAgent dispatch, Orchestrator parallel/sequential.

## Dependency

This project depends on `operator-shared-core` (sibling repo at `../operator-shared-core`).
The shared core provides:
- `shared_core.llm.LLMClientFactory` — async OpenAI/Anthropic client factory
- `shared_core.config.BaseAppConfig` — base Pydantic settings
- `shared_core.logging.setup_logging` — loguru-based structured logging
- `shared_core.errors.BaseApplicationError` + handler — exception base class

**Two install modes:**

- **Termux (default when `~/.hermes/hermes-agent/venv` exists):** PYTHONPATH only, no `pip install -e`. Run `bash scripts/install-termux.sh`.
- **Standard (Linux/macOS, or Termux without the venv):** `pip install -e .` from this directory.

See `Makefile` for the auto-detection logic. The Makefile picks the mode based on whether `~/.hermes/hermes-agent/venv` exists; this is overridable via the `ARIA_TERMUX=0` env var.
