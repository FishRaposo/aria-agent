# Failure modes

| Failure | Offline behavior | Evidence |
|---|---|---|
| Database unavailable | startup probe selects in-memory stores | `/health` reports degraded/offline |
| Redis or broker unavailable | API remains usable; worker is optional | worker import test |
| Provider key/SDK missing | deterministic simulated routing/response | demo and golden fixture |
| Unknown tool or invalid arguments | structured error, no side effect | tool and agent tests |
| Safety block | blocked result before routing | safety fixture |
| Rate limit exceeded | blocked result with deterministic reason | rate-limit fixture |
| Retry exhaustion | traced error after bounded attempts | retry tests |
| Approval timeout | pending record becomes expired on read/sweep | approval lifecycle tests |
| Replay | dry-run result with no side effects | replay endpoint/test |
| Evidence tampering | verifier exits non-zero with file-specific error | checksum tests |

The system favors a visible degraded result over silently widening authority.
