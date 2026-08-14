# Design decisions

## Local compatibility layer

The archived cross-project dependency was replaced with the exact server-used
subset under `aria.internal.vendor_core`, pinned and attributed in
`THIRD_PARTY_NOTICES.md`. Public ARIA imports remain facades so existing clients
do not need a coordinated migration.

## Offline-first defaults

Simulation, in-memory stores, one retry attempt, no rate limit, warning-only
safety, and single-step planning are the compatibility defaults. Optional local
capabilities are explicit settings rather than hidden behavior changes.

## Event-driven execution

Normal and SSE runs share `AgentEngine` and `RunEvent`. This prevents the stream
surface from inventing a second execution contract and makes event order part of
the evidence fixture.

## Evidence over feature breadth

The portfolio proof is a normalized, checksummed bundle. It records semantic
behavior while excluding runtime noise and redacting secrets. Hosted workflows,
webhooks, and provider infrastructure remain outside this repository's default
contract.
