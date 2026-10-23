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
| Concurrent approval | only one atomic claim can dispatch; loser receives conflict | memory/SQLite HTTP race regression |
| Changed arguments/run or expired/rejected approval | strict execution denied, no effect | boundary effect-counter tests |
| Crash after claim/effect | durable uncertain claim retained; no automatic redispatch | database dispose/reopen tests |
| Tool fails after an effect | consumed failed claim, no automatic retry | post-effect failure regression |
| Existing database without migration | apply additive migration before launch; do not rely on create_all | migration regression |
| Connected dashboard outage | visible connection error, Retry or explicit sample switch | API/browser regressions |
| Native CLI unavailable | all 60 benchmark cells unavailable, null native cost | fixture benchmark contract |

The system favors a visible degraded result over silently widening authority.
