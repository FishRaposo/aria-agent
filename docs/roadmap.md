# Roadmap

## Delivered local capabilities

- [x] Schema-validated tools and safe/approval-required permissions.
- [x] Deterministic and simulated/real provider routing with fallback.
- [x] Persistent-or-in-memory runs, memory, tasks, and approval lifecycle.
- [x] Internal vendored compatibility layer with attribution and wheel coverage.
- [x] Bounded multi-hop planning, deterministic safety checks, retries, and rate limits.
- [x] Ordered SSE events, dry-run replay, local hashed-vector memory search, and optional approval sweeping.
- [x] Offline evidence fixture, checksums, reproducibility hash, package checks,
  frontend unit/lint/build gates, and configured Chromium smoke coverage.
- [x] Progressive-disclosure Agent Skills with focused offline tests.
- [x] Immutable approval binding and durable single-use execution claims with
  a strict execution profile (boundary validation, no mode downgrade).
- [x] Packaged canonical skills with automatic per-run selection, immutable
  saved evidence, and explicit session memory with reconciled outcomes.
- [x] Connected console (Chat/Runs/Skills/Approvals/Memory) over real API/SQLite
  paths, verified by a real-process browser suite alongside the sample demo.

## Deferred product directions

- Actual native/model baseline/configured trials: runner delivered, runtime
  absent. No quality-improvement claim until authorized measured trials exist.
- Hosted PostgreSQL/provider validation and fresh Python3.11/Node20 CI for this
  milestone. Local verification uses a separate Python3.12 environment.

The portfolio milestone adds single-use execution claims, strict boundary
regressions, the self-contained native setup fixture and visual recruiter tour.
See [verification](portfolio-verification.md) for measured completion/limits.

- Hosted/team tenancy and workspace workflows.
- External notification/webhook delivery and hosted scheduling.
- OTLP protobuf/gRPC and hosted vector services.
- Mandatory Redis, PostgreSQL, or provider credentials.

These boundaries are intentional. The local abstractions exist to make the
engineering core reviewable without turning infrastructure into a prerequisite.
