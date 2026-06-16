# Design Decisions

Key architectural choices, in ADR (Architecture Decision Record) form. Each
records the context, the decision, and the consequences.

## ADR 1 — Offline-first, real-when-keyed

**Context.** A showcase must run on any machine with no credentials, yet still
demonstrate real provider integration.

**Decision.** Every external effect has a deterministic offline default and a real
path gated on configuration. The `AgentLLMClient` mirrors
`llm-cost-latency-monitor`'s SDK: a `mocked_response` short-circuits to a
simulated response; otherwise the real provider runs via
`shared_core.llm.LLMClientFactory`, falling back to mock on ImportError / no key.
The DB probe falls back to in-memory stores; `web_search` falls back to a canned
knowledge base.

**Consequences.** The demo and all 152 tests run with no network, DB, or keys.
The real paths exist and are reachable by setting env vars, but are never on the
critical path for CI.

## ADR 2 — Lean on `shared-core`, don't re-mock

**Context.** Several primitives (token pricing, latency percentiles, span schema,
config, DB session management, test mocks) are common across the portfolio.

**Decision.** Cost goes through `shared_core.llmmetrics` + `shared_core.pricing`;
tracing uses `shared_core.tracing.Span`/`SpanType`; persistence uses
`shared_core.database` `Base`/mixins/`DatabaseManager`; tests use
`shared_core.testing.MockDatabase`/`MockRedisClient`. Golden tests assert our
cost numbers equal `shared_core.pricing.calculate_cost` so a shared-core change
that alters pricing surfaces as a test failure here.

**Consequences.** No duplicated pricing tables or span schemas; numeric results
stay consistent with sibling projects.

## ADR 3 — AST calculator instead of `eval()`

**Context.** The original calculator used `eval()` with restricted builtins — a
known-unsafe pattern.

**Decision.** Replace it with an `ast.parse(mode="eval")` walk that whitelists
only numeric literals and a fixed set of binary/unary operators. Names, calls,
attribute access, subscripts, and comprehensions are rejected. A `pow` exponent
cap guards against resource exhaustion (`9 ** 100000`).

**Consequences.** The tool cannot execute arbitrary code. Golden tests cover both
correct arithmetic and rejection of injection payloads.

## ADR 4 — Sandboxed file reader

**Context.** A file-reading tool is a classic path-traversal and secret-exfil
vector.

**Decision.** `file_reader` resolves every path against an allowlisted sandbox
root (`HERMES_SANDBOX_DIR`, default `./sandbox`) and verifies the resolved path
is contained within it via `Path.is_relative_to`. Absolute paths and `..`
traversal are rejected; only UTF-8 text up to a byte cap is returned.

**Consequences.** Even a fully LLM-controlled path argument cannot escape the
sandbox. Parametrized tests assert traversal payloads never leak outside content.

## ADR 5 — Permission levels + a real approval queue

**Context.** "Human-in-the-loop" is meaningless if the gate always returns `True`
(the original behaviour).

**Decision.** Tools declare a `Permission` (`safe` / `requires_approval`). In
`approval_gated` mode, a risky tool creates a *pending approval* in a store with
a timeout; the run pauses and returns the approval id. Approve/reject transition
the record and (for approve) execute the gated tool. The lifecycle is identical
across in-memory and DB backends.

**Consequences.** Risky actions cannot silently auto-execute under gating.
Approvals are first-class, queryable resources that survive restarts when a DB is
present.

## ADR 6 — DB-default with in-memory fallback via a startup probe

**Context.** Persistence is desirable but must not be a hard requirement for the
demo/tests.

**Decision.** A 2-second connect-timeout probe selects the backend at startup.
Stores share an interface (dict-returning), so the rest of the app is backend
agnostic. The probe uses a throwaway engine and lazy driver import, so importing
`db.py` never needs Postgres.

**Consequences.** One code path, two backends. Persistence is opt-in by simply
making a database reachable; nothing else changes.

## ADR 7 — Dual routing with keyword fallback

**Context.** Pure keyword routing is brittle; pure LLM routing needs keys and can
hallucinate tools.

**Decision.** `LLMRouter` is the default (`auto`) but always validates the chosen
tool against the registry and falls back to `KeywordRouter` on no decision /
invalid JSON / unknown tool / exception. The keyword router orders intents so
ambiguous phrasing resolves predictably.

**Consequences.** Routing is robust offline and online, and a misbehaving LLM
degrades to deterministic behaviour rather than crashing or calling a bogus tool.

## ADR 8 — Backward-compatible agent surface

**Context.** The original tests and demo call `HermesAgent(registry, gate).run(query)`
and expect a string.

**Decision.** Keep `run()` returning a string; add `run_structured()` returning a
`RunResult` for the API. The legacy `ApprovalGate.request_approval()` boolean API
is retained alongside the new queue-backed `evaluate()`.

**Consequences.** No breakage of the original contract while exposing the richer
structured result the API and dashboard need.
