# Security and trust boundaries

ARIA is a portfolio harness, not a hosted multi-tenant service. The default
configuration is offline and credential-free.

## Tool boundary

Every tool has a Pydantic input schema and a permission. Read-only tools are
`safe`; task and email artifacts are `requires_approval`. In `approval_gated`
mode a risky call creates a pending record and stops. Approval expiry is
materialized lazily or by the Celery/local sweeper. Replay is dry-run unless a
caller explicitly opts in.

## Prompt-injection checks

`SafetyClassifier` performs deterministic checks for common instruction override
patterns in the query, context, and tool arguments. `warn` records a high-risk
assessment and continues; `block` returns a blocked result before routing;
`off` preserves legacy behavior. This is a guardrail, not a complete content
moderation system.

## Secrets and evidence

Provider keys are read from typed environment settings and never placed in the
golden fixture. Evidence redacts secret-shaped keys and common bearer/API-key
patterns, and excludes paths, IDs, timestamps, and durations from its
reproducibility hash. Review `manifest.json` and `checksums.sha256` before
sharing an artifact.

## Deployment boundary

The API has no hosted authentication or tenant isolation. Put it behind an
appropriate gateway before exposing it outside a trusted local environment.
PostgreSQL, Redis, Celery, provider clients, web search, and Docker are optional
integration surfaces and are not required for the offline demo.
