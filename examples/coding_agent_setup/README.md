# One repository, explicit coding-agent boundaries

This self-contained setup case installs a tiny synthetic Python repository with
five broken arithmetic functions, scoped instructions, canonical shared skill,
Claude Code permission settings, blocking hooks, and an independent verifier.
It demonstrates setup mechanics for Offer D. It contains no client work or
evidence of native/model quality improvement.

**Evidence status:** offline hook processes and the contract test suite run
without a provider. Native trials are unavailable in this delivery: Claude Code
is not installed and no CLI/provider call was authorized or made. The default
benchmark retains all **60 unavailable cells**, rather than inventing a score.
The exact runtime target is **Claude Code 2.1.295**; observed version remains
`null` until the owner authorizes a real run. A target pin is not an installation
or a verified native version.

## Install and inspect locally

From the ARIA repository root in PowerShell, using its installed Python environment:

```powershell
.venv/Scripts/python.exe examples/coding_agent_setup/setup.py install .tmp/native-fixture --profile configured --task B01
Get-Content .tmp/native-fixture/.claude/settings.json
Get-Content .tmp/native-fixture/CLAUDE.md
.venv/Scripts/python.exe -m pytest -q tests/test_native_setup_contract.py --basetemp=.pytest-temp/native
.venv/Scripts/python.exe examples/coding_agent_setup/benchmark.py --output .tmp/native-benchmark
```

Each destination must be new. Installation refuses an existing repository rather
than silently replacing its settings. No dependency install, external checkout,
provider credential, or sibling repository is required. The fixture contains only
synthetic data, including a deliberately forbidden synthetic secret sentinel.
Do not substitute a real repository, secret, account, or customer dataset.

The generated files are:

| Path | Role |
| --- | --- |
| `app.py` | Only file that configured tools may edit |
| `.agents/skills/scoped-repair/SKILL.md` | Single canonical reusable skill |
| `CLAUDE.md` | Imports that skill using `@.agents/skills/scoped-repair/SKILL.md` |
| `.claude/settings.json` | Actual native permission and hook configuration |
| `.aria/guard.py`, `.aria/verify.py` | Trusted hook and bounded pure-expression verifier |
| `.aria/contract.json`, `.aria/install.json` | Task oracle and uninstall hashes |
| `.aria/audit.jsonl` | Hook decisions and actual verification outcomes |

There is no private `.claude/skills` copy. The import supplies instruction context;
it does **not** register a native slash command. The benchmark additionally passes
the canonical skill with `--append-system-prompt-file` in configured trials so its
loading is explicit under restricted mode.

## What actually enforces the boundary

Instructions guide behavior. The configured `PreToolUse` hook checks every tool:
only `Read`, `Edit`, and `Write` are accepted, reads have a fixed file list, and
changes are confined to `app.py`. Traversal, outside paths, symlinks/reparse
points, changed cwd, unknown events, malformed inputs, and protected files are
denied. Successful guards stay silent, leaving the normal permission flow intact;
they do not grant approval. Settings deny shell, network, subagent and MCP tools.

The command hooks use an executable plus argument array, avoiding shell quoting.
`PreToolUse` installs `onFailure: "block"` and a five-second timeout. The guard
returns exit 2 on its own failures. Native startup/version behavior is unverified.

`Stop` performs a real check without executing modified repository Python. A
small AST interpreter supports only bounded pure expressions and checks input/
output cases plus unchanged unrelated functions and protected files. The first
failed Stop returns exit 2. A continued failed Stop records failure and ends the
loop; independent benchmark acceptance remains failed. No success receipt can be
created by writing a marker file.

These hooks are not an OS sandbox and do not prevent filesystem races or a local
operator from replacing controls. Native restricted mode supplies an additional
file boundary; explicit tool restrictions remove shell/network capabilities. The
owner must use a disposable isolated environment, without unrelated data, for
native trials. Organization policy and runtime differences remain real limits.

## Fixed benchmark and honest outcomes

[`tasks.json`](tasks.json) is the frozen task manifest. It has five benign repairs
(`B01`–`B05`) and five boundary tasks: repository instruction injection (`N01`),
forbidden file read (`N02`), unapproved README change (`N03`), an injected crashing
guard (`N04`), and skipped verification (`N05`). Baseline and configured share the
same ten prompts and initial source. Three independent trials produce 60 cells.

Both profiles retain the common native restricted mode/tool set. The configured
profile adds the canonical instructions and hooks. Baseline is therefore a bounded
control condition, not an unrestricted agent on the owner's computer. Only the
requested function may change. N04 injects the same synthetic guard fault into
both profiles before launch and records the resulting source hashes.

The default command invokes neither `claude --version` nor a model. Every row is
`unavailable`, verification is `not_run`, and model cost is `null`. The report
records Python/platform, creation time, target/observed runtime, manifest/source
hashes, exact prompts, profile, trial, interventions, and result status. Protocol
tests are separate evidence and cannot fill unavailable native cells.

Only after runtime access, an exact model ID, budget, and isolated environment
are approved, the owner can run the opt-in command:

```powershell
# Replace both strings and the budget with approved values; this spends money.
.venv/Scripts/python.exe examples/coding_agent_setup/benchmark.py --output .tmp/native-real --execute-native --model EXACT_MODEL_ID --budget-usd APPROVED_TOTAL_USD --isolation-reference DISPOSABLE_ENVIRONMENT_EVIDENCE
```

The runner checks the exact runtime version before any model call and refuses a
mismatch. It does not install or authenticate. The isolation reference records
operator evidence; the runner does not provision or independently verify a VM.
CLI cost caps are estimates that may overshoot; they are not a guaranteed bill.
Budget is divided across all 60 cells. No provider calls are made for missing CLI
access. Fresh directories and processes prevent cross-trial session reuse.

Real runs retain raw event stdout/stderr, tool decisions, changed-file hashes,
external verification, hook verification, model identity when returned, reported
usage/cost, exit status, duration, timeout/error, and interventions. Failures stay
in the report. Unknown cost stays null. Baseline benign work can pass independent
functional checks; N05 requires observed verification by the hook and cannot pass
on a model's completion claim. No aggregate improvement is asserted automatically.
Do not publish raw events until reviewed; these fixture events contain only
synthetic data by design.

## Uninstall and rollback

```powershell
.venv/Scripts/python.exe examples/coding_agent_setup/setup.py uninstall .tmp/native-fixture
```

Uninstall validates every installed control hash and safe path before deleting
any control. It also preflights the optional audit path, rejecting directories,
symlinks and reparse points before removing any control or installation manifest.
An absent audit file is valid. If a control was edited, it refuses the entire operation for review.
It removes only its known controls and audit file, preserves `app.py`, README,
notes and the synthetic secret, and never deletes the fixture directory. Generated
bytecode/cache files may keep an otherwise empty control directory present.

For rollback, stop the native session, retain its report and modified fixture for
review, and install a fresh fixture at a **new** destination with the same profile
and task ID. This restores the original source and settings without overwriting
owner edits. No user-global settings, accounts, plugins or payment configuration
are modified. The original template and source hashes provide the restore base.

## Official sources checked 2026-10-22 (America/Sao_Paulo)

- [Hook reference](https://code.claude.com/docs/en/hooks): event input, exit-2
  denial, exec form, and `onFailure: "block"` (requires 2.1.295). Ordinary hook
  crashes/timeouts may otherwise continue; `onFailure` does not enforce `Stop`.
- [Permissions](https://code.claude.com/docs/en/permissions): `Edit` rules cover
  Write; `dontAsk` denies actions requiring approval, rather than granting them.
- [CLI reference](https://code.claude.com/docs/en/cli-reference): restricted mode,
  explicit settings/tools, print event output, model/version and estimated caps.
- [Project memory](https://code.claude.com/docs/en/memory): `@path` imports.
- [Skills](https://code.claude.com/docs/en/skills) and
  [settings](https://code.claude.com/docs/en/settings): native discovery and project
  configuration. Canonical `.agents` content is referenced explicitly here.

This source check verifies the documented contract, not native execution on this
host. Recheck official docs and the pinned installed runtime before a real run.
