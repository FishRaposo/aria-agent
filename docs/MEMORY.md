# Local memory

Conversation memory retains the existing bounded in-memory/SQLAlchemy behavior.
`LocalVectorIndex` is a pure-Python hashed-vector index for deterministic local
inspection; it needs no model download. `GET /agent/memory/search` returns
record IDs, content, and stable cosine-like scores. Retrieval remains additive
and disabled as a required dependency by default.
