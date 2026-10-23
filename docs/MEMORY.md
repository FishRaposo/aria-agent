# Local memory

Conversation memory retains the existing bounded in-memory/SQLAlchemy behavior.
`LocalVectorIndex` is a pure-Python hashed-vector index for deterministic local
inspection; it needs no model download. `GET /agent/memory/search` returns
record IDs, content, and stable cosine-like scores. Retrieval remains additive
and disabled as a required dependency by default.

`GET /agent/memory` returns the actual per-session conversation the API writes:
user messages, agent responses, and once-only approval outcome events appended
through durable `event_key` deduplication. Reading memory reconciles saved
session history without dispatching tools, so a final outcome still appears
after restart even if the process stopped between execution persistence and
presentation. Each process's first reconciliation per session walks the full
saved history; subsequent walks only scan runs saved since that process's
latest reconciled boundary, with the boundary run re-checked so an outcome
persisted after the run's creation is never skipped. Immutable `event_key`s
make repeated projection harmless. Session filters organize a trusted local
workspace; they are not authorization.
