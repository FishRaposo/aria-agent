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

## Deferred product directions

- Hosted/team tenancy and workspace workflows.
- External notification/webhook delivery and hosted scheduling.
- OTLP protobuf/gRPC and hosted vector services.
- Mandatory Redis, PostgreSQL, or provider credentials.

These boundaries are intentional. The local abstractions exist to make the
engineering core reviewable without turning infrastructure into a prerequisite.
