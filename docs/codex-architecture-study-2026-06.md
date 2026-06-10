# OpenAI Codex CLI — Architecture Study

**Studied:** 2026-06-10  
**Repo:** https://github.com/openai/codex  
**Head:** `13468115fc6443970b8bf521927fceaf58ad35c1` ("Guard core test subprocess cleanup")  
**Local path:** `~/work/codex-cli/` (shallow clone, depth=1)  
**Author:** Vinícius Raposo (FishRaposo) — for Aria architectural reference

> Aria is ~10K LoC of Python. Codex is ~1M LoC of Rust. Different leagues, but
> the sub-agent + role system is directly comparable.

---

## 1. Scale and shape

| | **Codex** | **Aria v0.4** |
|---|---|---|
| Total LoC | ~1,000,000 (Rust) | ~10,000 (Python) |
| Crates / modules | 125 crates | 7 modules |
| Core crate | `codex-core` (82K LoC, 245 files) | `aria_agent` |
| Main loop | `core/src/session/turn.rs` (2,250 LoC) | `aria_agent/agent.py` (v0.3) + `aria_agent/main.py` |
| Tests | ~50K LoC of test code | 131 tests, ~3K LoC |
| Native binary on Termux | ❌ (Rust + CGO + Linux-x86_64 wheel) | ✅ (pure-Python) |

**One thing to learn:** Codex modularizes via 125 Rust crates. Aria flattens into
7 Python modules. Both are valid; Aria's smaller surface is a feature on Termux,
where compile/install time matters.

---

## 2. The big one — sub-agents are data, not code

This is the architectural difference that matters most. Compare:

**Aria (code-driven):**

```python
# aria_agent/subagents/base.py
DEFAULT_ROLE_SPECS: dict[SubAgentRole, SubAgentRoleSpec] = {
    SubAgentRole.PLANNER: SubAgentRoleSpec(
        system_prompt="You are a planner. Decompose the task into steps…",
        temperature=0.7, max_tokens=4000, default_model=("opencode-go", "kimi-k2.6"),
    ),
    SubAgentRole.IMPLEMENTER: SubAgentRoleSpec(…),
    # … 9 hardcoded roles
}

SYSTEM_PROMPTS: dict[SubAgentRole, str] = {
    SubAgentRole.PLANNER: "You are a planner. Decompose the task into steps…",
    # … hardcoded prompts
}
```

**Codex (data-driven):**

```toml
# codex-rs/core/src/agent/builtins/awaiter.toml
background_terminal_max_timeout = 3600000
model_reasoning_effort = "low"
developer_instructions = """
You are an awaiter.
Your role is to await the completion of a specific command or task
and report its status only when it is finished.
…
"""
```

```rust
// codex-rs/core/src/agent/role.rs:42
pub(crate) async fn apply_role_to_config(
    config: &mut Config,
    role_name: Option<&str>,
) -> Result<(), String> {
    let role = resolve_role_config(config, role_name)
        .cloned()
        .ok_or_else(|| format!("unknown agent_type '{role_name}'"))?;
    apply_role_to_config_inner(config, role_name, &role).await
}
```

**Key design points in Codex's approach:**

1. **Each role is a TOML file** with the same schema as `config.toml`
2. **Roles are loaded into a config layer stack** — each role is a layer
   that can override model, provider, service_tier, sandbox, etc.
3. **Built-in roles live in source** (2 of them: `awaiter`, `explorer`)
4. **User-defined roles live on disk** at `~/.codex/agents/<name>.toml`
5. **The framework inserts the role layer at session-flag precedence**,
   so the role can override persisted config but the caller's current
   `model_provider` and `service_tier` remain sticky unless the role
   explicitly sets them.
6. **The role layer is rebuilt via `Config::load_config_with_layer_stack`**
   — same machinery as loading the main config, just one more layer

**What Aria could learn:** roles as TOML files. To add a new role, the user
edits a file — no code change, no test update, no release. Aria's 9 hardcoded
roles are a feature on day 0 (clarity, type safety) but a liability on day 100
(users can't customize without forking).

**Migration plan (future Aria work):**

- Move `DEFAULT_ROLE_SPECS` and `SYSTEM_PROMPTS` out of Python into
  `aria_agent/roles/builtins/*.toml` or `aria_agent/roles/*.toml`
- `SubAgentRoleSpec` becomes a Pydantic model loaded from TOML
- `SubAgentRegistry` looks up roles in `~/.aria/roles/` first, then built-ins
- `aria_subagent_tool` accepts `role_name` and a path to a user role file
- Tests change: instead of testing the Python constants, test the TOML loader

---

## 3. Agent names — cultural, memorable

Codex ships with a list of ~100 historical scientist/philosopher names for
sub-agents (from `codex-rs/core/src/agent/agent_names.txt`):

```
Euclid, Archimedes, Ptolemy, Hypatia, Avicenna, Averroes, Aquinas,
Copernicus, Kepler, Galileo, Bacon, Descartes, Pascal, Fermat,
Huygens, Leibniz, Newton, Halley, Euler, Lagrange, Laplace, Volta,
Gauss, Ampere, Faraday, Darwin, Lovelace, Boole, Pasteur, Maxwell,
Mendel, Curie, Planck, Tesla, Poincare, Noether, Hilbert, Einstein,
Raman, Bohr, Turing, Hubble, Feynman, Franklin, McClintock, Meitner,
Herschel, Linnaeus, Wegener, Chandrasekhar, Sagan, Goodall, Carson,
Carver, Socrates, Plato, Aristotle, Epicurus, Cicero, Confucius, …
```

**This is delightful.** The agent's *name* and its *role* are decoupled:

- Name: "Turing" (or "Euclid" or "Sagan") — picked from the list
- Role: "default" (or "awaiter" or "explorer") — loaded from TOML
- Each spawned agent gets a friendly name that the user can refer to in
  follow-up messages ("@Turing, what did you find?")

Aria currently uses role names ("planner", "implementer") as identifiers.
That's descriptive but dry. A name + role split would:
- Make spawn outputs more human ("Turing the planner started…")
- Let users give sub-agents a persona when they care
- Match Codex's UX and Claude Code's "Task tool" UX

**Migration plan:** `SubAgent.nickname` field, picked from a `nicknames.txt`
list. User can override at spawn time.

---

## 4. Sub-agent API surface

Codex has 7 sub-agent tools. Aria has 2 (single + orchestrator).

| Codex tool | What it does | Aria equivalent |
|---|---|---|
| `spawn_agent` | Spawn one sub-agent with role + initial message | `POST /subagent/run` |
| `send_message` | Send a message to a running sub-agent | ❌ missing |
| `wait_agent` | Block until a sub-agent finishes | `POST /subagent/run` (sync) |
| `list_agents` | List active sub-agents | `GET /subagents` |
| `interrupt_agent` | Cancel a running sub-agent | ❌ missing |
| `followup_task` | Hand off work after a sub-agent finishes | ❌ missing |
| `spawn_agents_on_csv` | Fan out: one sub-agent per CSV row | ❌ missing |

**Aria is missing 5 of 7.** The most interesting one is
`spawn_agents_on_csv` — it's a batch tool that takes a CSV file and
spawns one sub-agent per row, then reports results as a CSV back. This
is the "massively parallel data processing" pattern.

```rust
// codex-rs/core/src/tools/handlers/agent_jobs/spawn_agents_on_csv.rs
pub struct SpawnAgentsOnCsvHandler;
// Spans 316 LoC
// Reads CSV, spawns one sub-agent per row, returns CSV of results
```

**Migration plan for Aria v0.5:**

- `send_message` → Aria sub-agents are currently fire-and-forget. To add
  message passing, the SubAgent would need a persistent inbox and the
  Orchestrator would need to expose `agent_id`s in its return value.
- `interrupt_agent` → Aria sub-agents are wrapped in `asyncio.Task`; need
  a `cancel()` call. The `cancellation_token` pattern from Codex is cleaner
  than ours (use `asyncio.CancelledError` propagation).
- `spawn_agents_on_csv` → Aria can do this in <100 LoC. The orchestrator
  just calls `run_parallel` with a list of tasks.

---

## 5. Sub-agent lifecycle events

Codex's protocol has 11 dedicated event types for sub-agents
(`protocol/src/protocol.rs:1520-1580`):

```
CollabAgentSpawnBegin
CollabAgentSpawnEnd
CollabAgentInteractionBegin
CollabAgentInteractionEnd
CollabWaitingBegin
CollabWaitingEnd
CollabCloseBegin
CollabCloseEnd
CollabResumeBegin
CollabResumeEnd
SubAgentActivity
```

These are emitted by the runtime and consumed by the TUI/app-server/SDK.
The TUI uses them to show per-sub-agent status. The app-server uses them
to stream events to clients. The SDK uses them for observability.

**Aria's `SubAgentResult` is just a final result.** Aria doesn't emit
intermediate events. If a sub-agent takes 30 seconds, the user just
sees "loading…" with no progress. Adding `SubAgentEvent` streaming
(begin, progress, intermediate message, end) would be a big UX win
without a big code change.

**Migration plan:** `aria_agent.subagents.SubAgent.run()` becomes
`async def run(...) -> AsyncIterator[SubAgentEvent]` — the user
gets a stream of events, the FastAPI endpoint streams them via SSE
(Server-Sent Events). The TUI can render live activity per role.

---

## 6. Aria has what Codex doesn't: task-type routing

Codex's model selection is **explicit** — you set `model = "gpt-5"` in
`config.toml` or pass `--model gpt-5` on the CLI. There's no "task type →
best model" decision tree.

Aria's `RoutingTable` is **declarative data** that says:
- `TaskType.CODE_REVIEW` → qwen-3.7-max (best quality, code review)
- `TaskType.LONG_CONTEXT` → minimax-m2.7 (1M context, default)
- `TaskType.CODING_DEFAULT` → MiniMax-M3 (best TB on Go plan)
- `TaskType.REASONING` → kimi-k2.6 (high TB, vision)
- …

Aria's `select(task_type)` then ranks candidates by tier + TB score + cost.
The `ProviderRegistry.resolve_decision()` ensures every pick is *callable*
on the user's plan (phantom-model defense).

**This is Aria's unique strength.** Don't lose it. But the cost is that
Aria hardcodes providers and models in `routing_table.py` — see #9 below.

**Two orthogonal axes Codex has that Aria doesn't:**

1. **Reasoning effort** (`None`, `Minimal`, `Low`, `Medium`, `High`, `XHigh`,
   or `Custom(String)`). Cheap models with high effort > expensive model
   with low effort, sometimes. Aria currently passes `temperature` but
   not reasoning effort.
2. **Service tier** (`Fast`, `Default`, `Flex`, `Priority`). Different
   latency/throughput for the same model. Aria passes neither.

**Migration plan:** add `ReasoningEffort` and `ServiceTier` to
`ModelInfo`, and to `SubAgent` + `Orchestrator` request schemas.
`select_for_role` should accept `effort` and `tier` as additional
selection criteria. Default to whatever the model recommends.

---

## 7. Provider philosophy — opposite of Aria

From `codex-rs/model-provider-info/src/lib.rs:421-423`:

> "We do not want to be in the business of adjudicating which third-party
> providers are bundled with Codex CLI, so we only include the OpenAI and
> open source ('oss') providers by default. Users are encouraged to add
> to `model_providers` in config.toml to add their own providers."

Codex ships with **4 providers**: OpenAI, Amazon Bedrock, Ollama, LM Studio.
Everything else is user-configured in `~/.codex/config.toml`:

```toml
[model_providers.kilo]
name = "Kilo Gateway"
base_url = "https://api.kilo.ai/v1"
env_key = "KILO_API_KEY"
wire_api = "responses"
```

Aria ships with **3 providers hardcoded** in `aria_agent/providers/*.py`:
`OpenCodeGoProvider`, `MiniMaxProvider`, `OpenAICodexProvider`. Adding a
new provider means writing a new Python class, registering it, updating
the registry, adding tests, releasing a new version.

**Aria could learn:** make providers config-driven. Each provider is a
TOML entry; Aria reads them at startup. The provider class becomes a
generic HTTP/chat-completions/Anthropic-SDK adapter that takes config.

**Migration plan:**

- `aria_agent/providers/opencode_go.py` becomes a generic
  `HTTPChatCompletionsProvider(config: ProviderConfig)` class
- Same for `MiniMaxProvider` (1M context, specific base URL) and
  `OpenAICodexProvider` (OAuth, different auth)
- Aria reads `[providers]` from `aria.toml` at startup
- The routing table no longer hardcodes `provider_name`; the router
  picks from registered providers and the registry validates
- Adding a new provider = add 5 lines to `aria.toml`, no code change

---

## 8. Built-in tool surface

Codex ships with **20+ tools** out of the box:

| Tool | Purpose | Aria equivalent |
|---|---|---|
| `apply_patch` | File editing (custom DSL) | ❌ missing |
| `shell` / `shell_command` | Bash execution | ❌ missing |
| `unified_exec` | Background shell with polling | ❌ missing |
| `view_image` | Image input | ❌ missing |
| `plan` | Todo list / plan | ❌ missing |
| `request_user_input` | Ask the user a question | ❌ missing |
| `request_permissions` | Permission escalation | `ApprovalGate` (v0.1, not wired) |
| `mcp` / `mcp_resource` | MCP protocol | ❌ missing |
| `multi_agents_*` (7 tools) | Sub-agents | `/subagent/*` (2 endpoints) |
| `agent_jobs` | Batch CSV sub-agents | ❌ missing |
| `tool_search` | Tool discovery | ❌ missing |
| `extension_tools` | Extension API | ❌ missing |

**Aria's 5 tools (calculator, web_search, file_reader, task_creator,
email_draft) are all v0.1 toy tools.** None of them are production-grade.
Aria v0.4 added sub-agents and routing but didn't add real tools.

**Migration plan for Aria v0.5+:**

- **`shell`** — bash execution, sandboxed. Critical. Use Termux's
  `proot` or `tsu` for sandbox if available, or just verify commands
  against an allowlist.
- **`unified_exec`** — long-running background process with polling.
  Lets Aria kick off `pytest` and check back.
- **`apply_patch`** — file editing with diffs. Aria's `file_reader` can
  read but not write.
- **`view_image`** — image input for vision models. Kimi-k2.6 supports
  it; Aria's `RequestItem.content` should accept image URLs.
- **`plan`** — Aria sub-agents could emit a plan as a structured tool
  call, then the orchestrator could show it to the user.

---

## 9. The full agent loop in `run_turn()`

`codex-rs/core/src/session/turn.rs:135` is the main agent loop. The
pattern is the standard LLM agent loop, but with care:

```rust
pub(crate) async fn run_turn(
    sess: Arc<Session>,
    turn_context: Arc<TurnContext>,
    …
) -> Option<String> {
    let mut client_session = …;  // turn-scoped, WebSocket-cached

    // 1. Pre-sampling: compact if needed
    run_pre_sampling_compact(&sess, &turn_context, &mut client_session).await?;

    // 2. Record context + drain pending input
    sess.record_context_updates_and_set_reference_context_item(turn_context.as_ref()).await;
    let pending_input = sess.input_queue.get_pending_input(&sess.active_turn).await;

    // 3. Run hooks (session_start, before each turn)
    if run_hooks_and_record_inputs(&sess, &turn_context, &pending_input).await {
        return None;
    }

    // 4. The loop
    loop {
        // 4a. Build the sampling request from current history
        let sampling_request_input: Vec<ResponseItem> =
            sess.clone_history().await
                .for_prompt(&turn_context.model_info.input_modalities);

        // 4b. Call the model
        let sampling_request_output = run_sampling_request(
            Arc::clone(&sess), Arc::clone(&turn_context), …,
        ).await?;

        // 4c. Did the model need follow-up (tool calls)?
        let needs_follow_up = model_needs_follow_up || has_pending_input;

        if needs_follow_up {
            continue;  // back to 4a
        }

        // 4d. Token limit reached? Auto-compact.
        if token_status.token_limit_reached {
            run_inline_auto_compact_task(…).await?;
            continue;
        }

        // 4e. Otherwise, return
        return last_agent_message;
    }
}
```

**Aria's loop is the same shape but smaller.** The two big differences:

1. **Auto-compaction** — Codex's loop has a `run_inline_auto_compact_task`
   step that summarizes history when it gets too long. Aria has
   `compact.rs` (v0.2) but it's not wired into the loop. Without it,
   long conversations hit the model's context limit and the model
   starts losing the start of the conversation.
2. **Hooks** — Codex has a `hook_runtime` that runs user-defined code
   at session_start, before each turn, and on turn stop. Aria has
   nothing equivalent.

**Migration plan:** wire `compact` into the orchestrator's loop. Hooks
can wait for a use case (YAGNI).

---

## 10. Other notable patterns

- **Config layering** — Codex's `ConfigLayerStack` is the architectural
  idea. Multiple TOML files get merged with explicit precedence. The
  role system is just one more layer. Aria's config is a single
  Pydantic model — could benefit from layers.
- **Cancellation tokens** — `tokio_util::sync::CancellationToken` is
  threaded through the entire turn. Aria uses `asyncio.CancelledError`
  but doesn't have an explicit token to pass around.
- **MCP support** — Codex's `mcp.rs` is 1,800 LoC. Aria has zero MCP
  support. If clients ask for MCP, Aria will need it.
- **App-server protocol** — Codex has a separate `codex-app-server`
  binary that exposes the same protocol over HTTP/JSON-RPC for IDE
  integration. Aria is HTTP-only.
- **Analytics** — Codex has a full `analytics/` crate that emits
  structured events to a remote service. Aria has no analytics.
- **Memory/persistence** — Codex has a `state/` crate with a
  `runtime/memories.rs` (5,268 LoC) — long-term memory across
  sessions. Aria's `AgentMemory` is per-session only.

---

## 11. Top 3 things Aria should adopt

In order of value/effort:

### 🥇 Move roles to TOML (data-driven, user-extensible)

**Why:** Today's 9 roles are a feature; tomorrow's user needs role #10
without a code change. Codex proves this works.
**Effort:** 1-2 days. Touches `subagents/base.py`, `subagents/registry.py`,
`agent.py`, and the README.
**Risk:** low. Existing tests cover the Python data; new tests cover the
TOML loader. Roll back is a `git revert`.

### 🥈 Add a streaming `SubAgentEvent` API

**Why:** 30-second sub-agents with no progress is a bad UX. Codex's
11 lifecycle events let the TUI show "Turing the planner is reading
file X…" in real time.
**Effort:** 1 day. Changes `SubAgent.run()` signature to return
`AsyncIterator[SubAgentEvent]`. The FastAPI endpoint switches to SSE.
**Risk:** medium. The endpoint contract changes. Mitigate by keeping
the old `/subagent/run` as a wrapper that collects all events.

### 🥉 Add `spawn_agents_on_csv` as an Aria endpoint

**Why:** The "fan out one sub-agent per row of data" pattern is
massively useful for batch processing. Codex ships it; Aria doesn't.
**Effort:** <100 LoC. Wraps the existing `Orchestrator.run_parallel`.
**Risk:** low. Pure addition.

---

## 12. Top 3 things Aria should NOT adopt

### 🚫 Cargo's 125-crate workspace

Aria's 7 Python modules are a feature on Termux. Rust's compile times
and Termux's missing toolchain mean Aria-in-Rust would be a 2-day
install for every update. The complexity of 125 crates is justified
for a project with 100+ engineers; Aria is one person.

### 🚫 The full TOML config layer stack

Codex's `ConfigLayerStack` solves a problem Aria doesn't have:
"user might have 5 different sources of config (system, user, project,
flags, role) with conflicting precedence." Aria has "env var + a
Pydantic model." Adding layers is YAGNI until a user asks.

### 🚫 MCP, app-server, analytics, persistence

These are big features that each cost OpenAI 6+ months of engineering.
Aria should add them only when a paying client asks. For now, the
FastAPI gateway + SQLite (when needed) is enough.

---

## 13. What Aria has that Codex doesn't

| Feature | Aria | Codex |
|---|---|---|
| Cross-provider model routing | ✅ (TaskType → ModelInfo) | ❌ (CLI flag) |
| Cooperation patterns (cascade, plan-execute-validate, ensemble) | ✅ | ❌ |
| Phantom-model defense (`resolve_decision`) | ✅ | n/a (no catalog) |
| Sub-agent role → model mapping | ✅ (9 roles) | ❌ (1 default) |
| Budget override (cheap/balanced/quality) | ✅ | ❌ (reasoning effort is closest) |
| Cost tracking per call | ✅ (per-step tokens + cost) | ✅ (token usage only) |
| Production-tested on Termux | ✅ (131 tests pass) | ❌ (binary doesn't run) |
| Termux install script | ✅ (`scripts/install-termux.sh`) | ❌ |

**Don't lose the routing. It's the whole point of Aria.**

---

## 14. Files to look at for further study

- `codex-rs/core/src/agent/role.rs` — role layer system, **must-read**
- `codex-rs/core/src/agent/control/spawn.rs` — sub-agent spawn, 713 LoC
- `codex-rs/core/src/agent/registry.rs` — agent metadata + depth limits
- `codex-rs/core/src/agent/agent_names.txt` — the 100+ scientist names
- `codex-rs/core/src/agent/builtins/awaiter.toml` — example role TOML
- `codex-rs/core/src/session/turn.rs:135-260` — main agent loop
- `codex-rs/core/src/tools/handlers/multi_agents_v2/spawn.rs` — v2 spawn tool
- `codex-rs/core/src/tools/handlers/agent_jobs/spawn_agents_on_csv.rs` — batch spawn
- `codex-rs/model-provider-info/src/lib.rs:415-445` — built-in provider philosophy
- `codex-rs/protocol/src/openai_models.rs` — model metadata schema
- `codex-rs/protocol/src/protocol.rs:1520-1580` — sub-agent event types

## 15. Useful Codex references already in Aria's skills

- `autonomous-ai-agents/codex` — how to drive Codex from Hermes
  (PTY, exec mode, --full-auto, --yolo, worktrees, parallel issue fixing)
