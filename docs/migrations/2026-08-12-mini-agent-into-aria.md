# mini-agent skill capability migration into ARIA

On 2026-08-12, ARIA received a Python-native implementation of selected
progressive-disclosure skill behavior observed in the local `mini-agent` source
clone.

## Provenance

- Source repository: <https://github.com/FishRaposo/mini-agent.git>
- Source revision: `fd8c97ee10fb98d925c8416758e0cb99c6ea0d97`
- Source state reviewed: clean local `master` checkout at that revision
- License review: **unresolved**. The reviewed source revision has no `LICENSE`
  file and its `package.json` has no license declaration. No source code was
  copied; ARIA's implementation is a Python-native reimplementation of the
  selected behavior. Resolve licensing before copying or distributing any
  source material from that repository.

## Selected capabilities

- Required `name` and `description` validation for YAML-frontmatter
  `SKILL.md` files.
- Metadata-only discovery, optional eager activation hints, and explicit lazy
  instruction loading.
- Opt-in trusted project scope plus user and built-in scopes, with deterministic
  first-wins precedence and name deduplication.
- Bounded resource-path listing and explicit truncation evidence.
- Per-turn duplicate activation suppression and a structured context report.
- Offline operation with no API key, provider, CLI, database, or network
  dependency.

## Source-path mapping

| Reviewed source | ARIA destination | Treatment |
|---|---|---|
| `src/skills.js` | `src/aria/skills.py` | Reimplemented parsing, discovery, hints, lazy loading, scope precedence, and bounded resource listing in Python. |
| `src/agent.js` | `src/aria/skills.py`, `src/aria/agents.py` | Reimplemented explicit activation, same-turn deduplication, context reporting, and optional agent-session integration. |
| `src/tools.js` | `src/aria/skills.py` | Retained only bounded resource metadata used by activation; no shell, file-reading, or fetch executors were ported. |
| `test/skills.test.js` | `tests/test_skills.py` | Re-expressed selected observable contracts as offline pytest tests. |
| `README.md`, `AGENTS.md` | `README.md`, `AGENTS.md` | Added ARIA-specific usage and verification guidance. |

## Intentionally excluded

The Node CLI, provider adapters and SDK dependencies, provider tool loop, shell
command runner, arbitrary file reader, URL fetcher, console formatting, bundled
sample skills, and package/build material were not migrated. ARIA does not gain
new network calls or required services from this change, and its existing tool
permission and approval loop remains authoritative.

## Rollback and archive condition

Rollback is limited to removing `aria.skills`, its optional `AriaAgent`
integration and result field, its focused tests, and these documentation
updates. The local `mini-agent` source clone must remain available for
provenance until this mapping and the unresolved license review are preserved
in an accepted repository record or equivalent archive. This migration does
not authorize deleting, renaming, pushing, or remotely archiving either
repository.
