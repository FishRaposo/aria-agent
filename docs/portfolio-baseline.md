# Project 02 — ARIA implementation baseline

Recorded 2026-10-22 (America/Sao_Paulo). Plan: `portfolio/plans/aria-agent.md` in the parent operation workspace. Implementation branch: `feat/aria-portfolio`; starting commit: `ad5f6e94ee70ae0e9eabbe79d903f2993234ab0b`. The clean branch was refreshed with `git pull --rebase` before edits.

## Environment and reproducibility

- System Python: 3.14. Implementation uses a separate `.venv` created with the bundled Python 3.12.14, satisfying the project's >=3.10 declaration. Existing hosted CI uses Python 3.11; a local pass is not a new hosted CI result.
- Local Node: 24.21.0; npm: 11.19.0. Existing CI declares Node 20. The unchanged frontend lockfile was installed with `npm ci --no-audit --no-fund`.
- `.venv` was installed with the declared editable `.[dev]` extra. Raw local logs live in ignored `.tmp/baseline-*.log`; build artifacts are ignored.
- No Claude Code CLI was available. Native-runtime tasks/model outcomes must remain unavailable unless actually executed with explicitly authorized model/account use. No provider calls, publication, or paid service use were performed during baseline checks.

## Pre-change checks and observed results

| Check | Command / outcome |
| --- | --- |
| Original Python suite | `.venv/Scripts/python.exe -m pytest -q --basetemp=.pytest-temp/baseline`: 200 original tests collected; initial run hit 11 temporary-fixture setup errors because the parent `.pytest-temp` directory was absent, plus one namespace scanner failure reading generated runtime files |
| Focused skills | `pytest --noconftest tests/test_skills.py -q`: 12 passed; this is a subset, not added to the full-suite count |
| Ruff | `ruff check src/aria tests examples scripts`: clean; `ruff format --check ...`: 72 files formatted |
| Types | Initial relative-interpreter/sandbox attempt could not discover installed libraries (38 missing-import errors). Escalated subprocess access plus an absolute `--pythonpath` to the project interpreter yielded 0 errors and 0 warnings. No source change was needed to suppress type diagnostics |
| Existing evidence | `python scripts/portfolio_demo.py` followed by `python scripts/verify_portfolio_evidence.py`: generated and verified against the existing golden |
| Packaging | `python -m build --outdir .tmp/baseline-dist`: sdist and wheel built. This alone does not prove isolated wheel imports |
| Frontend tests | `npm test -- --run`: 10 files, 32 tests passed |
| Frontend lint/build | `npm run lint` and `npm run build`: both passed |
| Browser baseline | `npm run test:e2e -- --project=chromium`: six tests attempted but Chromium launch failed because the matching Playwright browser executable was not installed; no application assertion failure was established |

The original affected Python groups (`test_aria_namespace`, `test_tools`, `test_evidence`) were rerun after creating the local temp parent and excluding ignored generated caches from namespace scanning: all 64 passed. The forbidden-dependency scanner also passed. Full post-change gates are recorded separately; they must not be labeled as a pristine baseline.

## Confirmed behavior gaps

1. Concurrent approval: the existing HTTP-shaped `get pending → decide approved → execute` sequence permits two callers to dispatch one action because `decide` returns the already-approved record to the loser. A deterministic store/control-flow probe produced two simulated effects; the implementation regression must use actual HTTP handling and both memory/file-backed SQL stores.
2. Memory records expose mutable nested argument dictionaries. Binding must retain an independent snapshot and validate exact run/action/arguments before dispatch.
3. Strict policy is configuration-dependent; runtime requests must not downgrade a strict deployment into free-running execution. Existing legacy defaults remain compatible.
4. The connected frontend silently substitutes sample data after network errors, including approval decisions. Explicit sample selection must replace this behavior.
5. The browser test configuration relies on an unreachable backend to trigger fallback. Forced sample tests and connected error tests need separate explicit modes.
6. `next/font/google` creates a network dependency for the core preview; the implementation will use local/system typography.

## Harness repairs, not weakened assertions

Created `.pytest-temp` before invoking a nested `--basetemp`. Namespace and forbidden-dependency scans now exclude ignored `.tmp`, `.pytest-temp`, `.next`, environments, and generated build/artifact directories while retaining runtime source scanning. This avoids treating downloaded dependencies, caches, or transient build files as product source. Tests must still fail for forbidden identities/dependencies in actual runtime-facing files.

On this host, Windows sandbox child-process access affects Pyright, Vitest, Playwright, and temporary fixtures. Tests run with the necessary subprocess access; environment/setup failures are not counted as behavioral red tests or application defects.

## Acceptance still required after implementation

- Full Python and focused skills suites, formatting/lint/types, canonical evidence and the new strict proof, wheel content/import checks.
- Actual memory/SQL concurrent HTTP approval, immutable binding, expired/rejected/invalid action, and restart/no-retry checks.
- Native hook protocol/fixture tests; unavailable native model trials remain explicitly unavailable.
- Frontend unit/lint/build and browser journeys at three viewports, keyboard/reduced motion, zero-provider/backend sample operation, and honest connected failures.
- Reviewed screenshots, updated README/case study/walkthrough, plan checkboxes matching measured results, and final task-scoped diff/commit.
