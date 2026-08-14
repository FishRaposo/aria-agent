# ARIA local core decision — 2026-08-14

## Decision

Replace the archived sibling dependency with the exact server-used v1.3.0
subset vendored under `src/aria/internal/vendor_core/`, then put orchestration
behind `src/aria/internal/core/` while retaining public compatibility facades.

## Why

The portfolio piece must install, run, and produce evidence from a clean
checkout. A Git URL or sibling path makes the result non-reproducible and hides
the actual dependency boundary.

## Rejected alternatives

- Restoring the archived external package: violates self-containment and makes
  clean wheel verification meaningless.
- Rewriting every public module at once: creates avoidable wire and import
  churn; facades keep golden behavior reviewable.
- Making hosted services mandatory: contradicts the offline portfolio goal.

The source commit and attribution are recorded in `THIRD_PARTY_NOTICES.md`.
