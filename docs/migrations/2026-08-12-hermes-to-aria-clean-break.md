# Hermes to ARIA clean-break migration

On 2026-08-12, the framework moved from its historical Hermes name to ARIA.
Historical Hermes provenance is not the runtime identity: the package, service,
worker, configuration, examples, and public interface now identify only as ARIA.

This is an intentionally breaking migration with no compatibility aliases or
fallbacks:

- Python imports move from `hermes.*` to `aria.*`, and `HermesAgent` becomes
  `AriaAgent`.
- The package and service identity changes from `hermes-agent-framework` to
  `aria-agent-framework`.
- `HERMES_SANDBOX_DIR` becomes `ARIA_SANDBOX_DIR`, and
  `HERMES_SEARCH_API_URL` becomes `ARIA_SEARCH_API_URL`. The old environment
  variables are ignored.
- Celery task names move from `hermes.run_agent` and
  `hermes.sweep_expired_approvals` to `aria.run_agent` and
  `aria.sweep_expired_approvals`. Workers and producers must deploy the new task
  names together.

Consumers must update imports, environment configuration, worker commands, and
queued task names before upgrading. Existing source imports and queued messages
using the historical namespace are not supported after the migration.
