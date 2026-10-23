# ARIA: make authorization an execution boundary

ARIA lets a reviewer follow a proposed action from validated input through
permission, human decision, execution and trace. The visual sample makes that
sequence approachable; the Python project supplies the actual enforcement.
This is synthetic portfolio work, with no client, revenue or production-use claim.

## The defect and the change

At baseline `ad5f6e94ee70ae0e9eabbe79d903f2993234ab0b`, two HTTP requests could
observe the same pending approval, both receive an approved record, and both
dispatch its tool. The new regression uses a real counting tool, actual HTTP
handlers and memory/file-backed SQLite stores. It reproduced two effects where
one was authorized. The [baseline](portfolio-baseline.md) records host/setup limits.

An approval now binds an independent snapshot of action, JSON arguments, run
identity and expiry. A lock-protected or conditional database execution claim
must succeed before dispatch. The public decision remains `approved`; execution
has separate `claimed`, `completed` or `failed` metadata. Claim tokens are private.
Concurrent and stale handlers cannot redispatch a consumed action.

The claim commits before the effect. If a process disappears after dispatch,
`claimed` means the outcome is uncertain. ARIA does not retry that action
automatically. A failure can occur after a tool has already changed something;
`failed` also consumes the claim. This provides at-most-once dispatch for an
approval, not guaranteed exactly-once external effects or transaction rollback.
An operator must reconcile the external system before creating a new request.

The strict profile validates the tool and schema at the execution boundary,
rejects unbound/altered/expired/rejected actions, and keeps file reads inside the
workspace, including resolved symlink/junction escapes. A request cannot select
free-running mode to weaken a strict server. Legacy defaults/public facades remain.
Regex checks remain supplementary and are not universal injection protection.

## Two experiences, explicit evidence

- **Explore the demo:** run `npm run demo:ui` in `frontend/`. Tab-local synthetic
  scenarios explain success, review, rejection, expiry, single use and denial.
  No model or backend is needed. Sample actions simulate outcomes.
- **Run the actual project:** install the Python package, launch the strict API,
  create a risky action and decide it through the real approval endpoints.
  See the [walkthrough](portfolio-walkthrough.md). Connected failures remain
  errors; switching to sample data requires an explicit action.

The UI retains runs, approvals, tools, skills and chat. Catalog entries are
distinguished from activated skill content. Sample reset restores the entire
scenario state. Unsupported free text is explained instead of fabricated.

## Coding-agent setup proof

The [self-contained setup case](../examples/coding_agent_setup/README.md) adds a
tiny fixture repository, one canonical shared skill, native settings, blocking
hooks, bounded independent verification, rollback and a fixed benchmark runner.
Protocol tests exercise real local hook subprocesses without credentials.

Native Claude Code is absent. The 10-task × 2-profile × 3-trial report retains
**60 unavailable cells**, null cost and no native quality score. Passing local
protocol tests cannot establish model behavior. A real run needs the pinned
runtime, exact model, disposable environment and owner-approved budget. No paid
calls, native sessions, publishing or hosted deployment occurred in this milestone.

## Reproduce and inspect

Inspect the [approval timeline](images/portfolio-approval.png),
[denied action](images/portfolio-denied.png), [activated skills](images/portfolio-skills.png)
and [actual local connected result](images/portfolio-connected.png). These are
screenshots from the implemented application, not mockups.

Run the commands in [TESTS](TESTS.md), then:

```bash
python scripts/portfolio_demo.py
python scripts/verify_portfolio_evidence.py
```

The existing normalized golden stays unchanged. The same bundle adds
`strict-profile.json`, measuring one authorized effect, rejected duplicate,
zero denied effects and zero dry-run replay effects. Manifest hashes cover the
new file. HTTP concurrency, migration, durable restart and workspace containment
are verified separately in `tests/test_portfolio_boundaries.py`; the JSON proof
does not claim to exercise those mechanisms. Checksums detect drift, not authorship.

The [verification record](portfolio-verification.md) separates local results,
historical hosted CI, simulated preview and unavailable native execution. It
contains exact commands, counts, screenshots and environment limitations.

## Offer and interview story

For a coding-agent setup engagement, scope the repository, establish the allowed
actions, add canonical instructions and guards, preserve a rollback, then measure
fixed tasks with failures intact. For an audit/fix sprint, lead with the race:
reproduce the defect, explain why approving a record is insufficient, add the
atomic claim and demonstrate zero duplicate effects. Neither engagement should
promise unrestricted autonomy, universal injection resistance or a model-quality
improvement that has not been measured.

## Completing the connected application — 2026-10-23

The first portfolio milestone made execution boundaries inspectable, but the live
application did not yet retain skill/session evidence or reconcile approvals into
history. A successful sample walkthrough therefore could not establish live
workflow completeness. This milestone closes that gap: per-run automatic matching,
packaged canonical sources, immutable snapshots, session-isolated conversation
memory and authoritative outcome projection now back the visual console.

The interview story is a full lifecycle: calculate, inspect why instructions
loaded, review exact write arguments, approve once, observe the same outcome in
history/memory, then restart and inspect the original evidence. Counterexamples
include rejection, expiry, actual sandbox denial, storage failure and an uncertain
claim. No case silently turns failure into sample success. Real-process browser
checks query SQLite effect counts rather than trusting an optimistic dashboard.

This is local credential-free reliability evidence, not measured model quality,
hosted multi-user readiness or client adoption. [Connected design and setup](portfolio-connected.md)
and [fresh verification](portfolio-verification.md) provide the concrete review path.
