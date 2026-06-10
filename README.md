# Aria Agent

> **Cross-provider model router with cooperation patterns, a v0.1 tool agent, AND v0.4 role-based sub-agents.** v0.4 unifies all three: tool-friendly queries go to local tools, model-required queries go through a routed multi-model cooperation pattern, and complex multi-faceted work gets decomposed into specialist sub-agents (planner, architect, implementer, debugger, documenter, reviewer, tester, validator, researcher) — each backed by a model picked for that specific kind of work.

A FastAPI service that turns "I have a task" into either a local tool call, a routed multi-model response, OR a parallel/sequential fan-out of specialist sub-agents.

Part of a multi-project AI infrastructure portfolio (alongside `operator-shared-core`).

---

## At a glance

```bash
# Run the live demo (uses your OPENCODE_GO_API_KEY)
# Demos tool path + model path + sub-agent path
python examples/run_demo.py

# Single sub-agent — right tool for the job
curl -X POST http://localhost:8000/subagent/run \
  -H 'Content-Type: application/json' \
  -d '{"role": "planner", "task": "Plan a /health endpoint"}'
# → kimi-k2.6 (best for deep reasoning)

# Parallel orchestrator — independent perspectives
curl -X POST http://localhost:8000/orchestrator/run \
  -H 'Content-Type: application/json' \
  -d '{"task": "Design caching", "roles": ["planner", "architect", "researcher"], "mode": "parallel"}'
# → 3 sub-agents, all 3 models, max(individual) latency

# Sequential orchestrator — chained with context
curl -X POST http://localhost:8000/orchestrator/run \
  -H 'Content-Type: application/json' \
  -d '{"task": "Build /health", "roles": ["planner", "implementer", "validator"], "mode": "sequential"}'
# → planner → implementer (sees plan) → validator (sees both)
```

**3 execution paths:**

| Path | When | Latency | Cost |
|---|---|---|---|
| **Tool path** (v0.1) | Query matches a tool keyword (calculate/search/read/task/email) | <1ms | $0 |
| **Model path** (v0.2) | Single model + cooperation pattern (cascade, plan-execute, ensemble) | 1-30s | $0.001-$25 |
| **Sub-agent path** (v0.4) | Multi-role work: planner + implementer + reviewer, parallel or chained | 1-30s × N (sequential) or max (parallel) | $0.005-$50 |

**9 sub-agent roles, each with a specialist model:**

The router picks the best model per role. The table below shows each role's *preferred* model from the routing table; the actual call falls back through the registry's `resolve_decision` if the preferred one isn't on the user's plan.

| Role | Preferred model | Best for | Actual call on this plan |
|---|---|---|---|
| planner | kimi-k2.6 (best_quality) | Task decomposition, design thinking | kimi-k2.6 |
| architect | kimi-k2.6 | System design, broad thinking | kimi-k2.6 |
| implementer | MiniMax-M3 (default) | Production code | minimax-m2.7 (M3 needs direct key) |
| debugger | deepseek-v4-pro (long_context) | Root-cause analysis | kimi-k2.6 (deepseek is Pro+) |
| documenter | kimi-k2.6 | Technical docs, clear prose | kimi-k2.6 |
| reviewer | qwen-3.7-max (best_quality) | Code review, quality checks | kimi-k2.6 (qwen is Pro+) |
| tester | MiniMax-M3 | Edge-case test design | minimax-m2.7 |
| validator | qwen-3.7-max | Correctness verification | kimi-k2.6 (qwen is Pro+) |
| researcher | deepseek-v4-pro (long_context) | Synthesis from sources | kimi-k2.6 (deepseek is Pro+) |

The routing table is a *catalog* (what's preferred). The registry is the *reality* (what's callable on this plan). The two are separated by design — phantom models don't crash the system, they just fall through the decision chain.

**3 cooperation patterns (model path):**

| Pattern | When to use | Models called |
|---|---|---|
| `cascade` | Default. Try cheap first, escalate only if quality is low. | 1-2 |
| `plan_execute_validate` | Complex tasks where independent review matters. | 3 (planner + executor + validator) |
| `ensemble` | When you want multiple independent perspectives. | 1-N (parallel) |

**3 providers, 8+ routable models:**

- **OpenCode Go** (default) — 11 models including Kimi K2.6, DeepSeek V4 Pro, MiMo V2.5, GLM-5.1
- **MiniMax direct** — MiniMax-M3 (default session model), M2.7, M2.5
- **OpenAI Codex** (OAuth) — gpt-5.5 (Pro+ gated)

The router picks the best model per task AND per sub-agent role. Specialists beat generalists for specialty work. M3 is the default for general coding.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  FastAPI Gateway (POST /agent/run, /subagent/run, etc.) │
└────────────────────┬────────────────────────────────────┘
                     │
       ┌─────────────┼─────────────┐
       ▼             ▼             ▼
┌──────────────┐ ┌─────────────┐ ┌──────────────────────┐
│ AriaAgent    │ │ AriaAgent   │ │ Orchestrator         │
│ (v0.3)       │ │ (v0.3)      │ │ (v0.4)              │
│              │ │             │ │                      │
│ Tool path    │ │ Model path  │ │ Sub-agent path       │
│ (v0.1)       │ │ (v0.2)      │ │ (v0.4)              │
│              │ │             │ │                      │
│ KeywordRouter│ │ Cooperation│ │ SubAgent × N         │
│   + Tools    │ │   Pattern   │ │   + parallel/        │
│   + Approval │ │   + Router  │ │     sequential       │
│   (no LLM)   │ │   + Models  │ │   dispatch           │
└──────────────┘ └─────────────┘ └──────────────────────┘
       │             │                       │
       └─────────────┴───────────────────────┘
                     │
                     ▼
        shared_core.llm + Provider abstractions
```

**Per-request state.** The agent, registry, router, sub_agent_registry, and orchestrator are constructed once at app startup and shared across requests. No module-level mutable state per request.

**v0.4 unifies v0.1 (tools) + v0.2 (router/cooperation) + v0.3 (orchestrator) + v0.4 (sub-agents).** Three execution paths share the same provider registry, model router, and tool registry. Sub-agents add role-based model selection on top of the existing model routing.

**Sub-agents extend (not replace) cooperation patterns.** Cooperation patterns orchestrate multiple *model calls*. Sub-agents orchestrate multiple *roles*, each of which is one or more model calls. You can compose them: e.g., a sub-agent's `plan_execute_validate` cooperation uses the planner role for the planner step, the implementer role for the executor, and the validator role for the validator.

## Quick start

## Quick start

### Termux (recommended — no `pip install`)

Aria Agent is designed to run on Termux out of the box. The install script
detects the hermes-agent venv and uses PYTHONPATH — no `pip install -e` of
shared-core needed.

```bash
# One-time setup (idempotent — re-run anytime to verify)
cd ~/work/aria-agent
bash scripts/install-termux.sh

# Run the test suite (no API calls)
make test

# Run the live demo (needs OPENCODE_GO_API_KEY in your env)
source ~/.hermes/.env   # your existing Hermes env
make demo

# Start the FastAPI server
make serve
```

The `make` command auto-detects Termux mode: if `~/.hermes/hermes-agent/venv`
exists, it uses that Python + sets `PYTHONPATH` to find `shared-core`.
Standard (Linux/macOS) install is also supported via `make install`.

### Standard install (Linux / macOS / dev container)

```bash
cd ~/work/aria-agent
# Install aria-agent and shared-core (sibling project)
pip install -e ../operator-shared-core
pip install -e .

# Run tests
make test

# Run the live demo (needs OPENCODE_GO_API_KEY)
python examples/run_demo.py

# Run the server
uvicorn aria_agent.main:app --host 0.0.0.0 --port 8000
```

### Why PYTHONPATH on Termux?

Termux's network is slow. `pip install -e ../operator-shared-core` would
download sqlalchemy, pgvector, redis, and other deps that aria-agent
doesn't actually use. The hermes-agent venv already has every dep aria-agent
needs, and the install script wires it up via `PYTHONPATH` alone. Zero
downloads, zero install — and the import path is identical to a real install.

---

## API

### `POST /agent/run`

Run a task through a cooperation pattern.

```json
{
  "task": "Write a Python function to add two numbers",
  "pattern": "cascade",   // or "plan_execute_validate" or "ensemble"
  "budget": "balanced"    // or "cheap" or "quality"
}
```

Response:

```json
{
  "final_output": "...",
  "pattern": "cascade",
  "num_steps": 2,
  "num_models_used": 2,
  "total_cost_usd": 0.0054,
  "total_latency_ms": 6104.3,
  "steps": [...],
  "metadata": {
    "cascade_outcome": "escalated",
    "cheap_quality_reason": "Output too short (2 chars, want >= 20)",
    "cheap_model": "opencode-go/mimo-v2.5",
    "escalation_model": "opencode-go/kimi-k2.6"
  }
}
```

### Other endpoints

- `POST /agent/route` — preview which model would be picked (no API call)
- `GET /agent/patterns` — list available cooperation patterns
- `GET /models` — list all routable models with metadata, grouped by provider
- `GET /providers` — list configured providers + health status
- `GET /health` — overall health check

---

## Configuration

Environment variables (read at startup):

| Var | Effect |
|---|---|
| `OPENCODE_GO_API_KEY` | Enable OCG provider (default) |
| `MiniMax_API_KEY` | Enable MiniMax direct provider |
| `OPENAI_CODEX_OAUTH_TOKEN` | Enable OpenAI Codex provider (OAuth) |
| `DEFAULT_COOPERATION_PATTERN` | `cascade` (default) / `plan_execute_validate` / `ensemble` |
| `LOG_LEVEL` | `INFO` (default) / `DEBUG` / `WARNING` |

Providers are constructed lazily — only when their key is set.

---

## What v0.4 (current) does differently from v0.1

**v0.1** (the original agent framework):
- Single-model tool dispatch
- Keyword routing
- 5 toy tools (calculator, web_search_mock, etc.)
- Module-level mutable state (shared memory + cost tracker across all requests)
- Fake cost tracking (hardcoded "gpt-4o-mini" + 100/50 tokens)
- Dead `max_steps` loop (returned after first tool call)
- Documented 5 endpoints, 4 of which were stale

**v0.2** (intermediate):
- Cross-provider model routing (3 providers, 8+ models)
- Cooperation patterns: cascade, plan-execute-validate, ensemble
- Per-request state (no shared mutable singletons)
- Real cost tracking (per-step tokens, model-specific pricing)
- 6 endpoints, all live and documented
- 59 tests covering provider layer, router, cooperation patterns, and agent

**v0.3** (intent classification):
- `AriaAgent` orchestrator that classifies intent → routes to tool path or model path
- New endpoints: `/agent/intent`, `/agent/tools`
- Preserved v0.1's KeywordRouterAgent as a back-compat alias (`AriaAgent` in the legacy module)
- 98 tests

**v0.4** (this version — sub-agents):
- 9 specialist sub-agent roles, each with a model picked for that specific kind of work
- `SubAgent` (single role) + `SubAgentRegistry` (role → SubAgent) + `Orchestrator` (parallel/sequential dispatch)
- 5 new endpoints: `/subagents`, `/subagent/run`, `/orchestrator/run`, `/orchestrator/roles`, plus `/health` extended
- `ProviderRegistry.resolve_decision()` — the registry now falls back through the decision chain to the next *callable* model if the preferred one isn't on the user's plan
- `ModelInfo.role_preferences` and `RoutingTable.find_by_role` — data-driven role → model mapping
- `select_for_role(budget="cheap"|"balanced"|"quality")` — budget override at role level
- 131 tests (32 new in v0.4)

---

## Project layout

```
aria-agent/
├── src/aria_agent/
│   ├── providers/       # 3 providers + base + registry
│   │   ├── base.py
│   │   ├── openai_compatible.py
│   │   ├── minimax.py
│   │   ├── opencode_go.py    # handles chat-completions + Anthropic SDK
│   │   ├── openai_codex.py
│   │   └── registry.py
│   ├── router/          # routing table, classifier, selector
│   ├── cooperation/     # 3 patterns: cascade, plan_execute, ensemble
│   ├── agent.py         # AriaAgent orchestrator
│   ├── main.py          # FastAPI gateway
│   └── config.py
├── tests/               # 131 tests across 7 modules
├── examples/
│   └── run_demo.py      # Live demo with real OCG API
├── scripts/
│   └── install-termux.sh # Termux setup (idempotent, no pip install)
├── Makefile             # Auto-detects Termux vs standard
├── pyproject.toml
└── README.md
```

---

## Roadmap

- [x] Cross-provider model router (v0.2 — shipped)
- [x] Intent classification (v0.3 — shipped)
- [x] Sub-agent roles with role-specific model delegation (v0.4 — shipped)
- [x] Parallel + sequential orchestrator (v0.4 — shipped)
- [x] ProviderRegistry.resolve_decision() with provider-registered fallback (v0.4 — shipped)
- [ ] LLM-backed task classifier (replace rule-based v1)
- [ ] Self-consistency / voting ensemble (replace length-based winner pick)
- [ ] Persistent trace + cost history (PostgreSQL backend)
- [ ] Real approval gate (currently the system is "auto-approve everything")
- [ ] Multi-tenant state (currently per-process, not per-user)

---

## License

See [LICENSE](LICENSE) for details.
