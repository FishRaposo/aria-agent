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

The strict portfolio launch sets both `AGENT_MODE=approval_gated` and
`ARIA_SAFETY_MODE=block`. Request bodies cannot downgrade that deployment.
Execution validates registered tool, strict schema and workspace containment;
tool/repository text cannot grant permission. Approvals bind action, copied
arguments, run and expiry. Atomic single-use claims prevent duplicate dispatch
across concurrent handlers. Approval status remains distinct from execution.

The database migration is additive (`alembic upgrade head`). Old unbound rows
fail closed. A claim left after a crash is uncertain, never automatically
retried; failed calls also remain consumed because an effect may have preceded
failure. This is at-most-once dispatch, not exactly-once external delivery.
The local API has no user authentication and must stay on a trusted local host.
Connected browser use opts into explicit `CORS_ALLOWED_ORIGINS` (for example,
`http://localhost:3000`). Default CORS is disabled; no wildcard or browser
credentials are enabled. CORS is not an authorization mechanism.
Path checks and native hooks are not an OS sandbox or protection against a local
operator replacing controls. See [native setup limits](../examples/coding_agent_setup/README.md).

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
