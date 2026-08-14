# Compatibility layer

ARIA owns its runtime compatibility boundary. The vendored modules are pinned
to the archived v1.3.0 source commit recorded in `THIRD_PARTY_NOTICES.md`; they
are packaged inside the wheel and imported through `aria.internal.vendor_core`.

The public facades intentionally retain existing imports and wire contracts:
`RunResult`, `RouteDecision`, approval states, cost summaries, trace entries,
worker task names, and the progressive-disclosure skill API. New fields and
endpoints are additive. The SDK/demo does not need the archived package or a
sibling checkout.
