# Portfolio evidence

`make evidence` runs `scripts/portfolio_demo.py` and then
`scripts/verify_portfolio_evidence.py`. The ignored bundle contains:

- `manifest.json` — schema version, mode, Git SHA, suite/result/reproducibility hashes, and file digests;
- `report.json` — canonical redacted result;
- `report.md` — human-readable view;
- `strict-profile.json` — measured in-memory authorization/single-use/denial and dry-run replay effects;
- `checksums.sha256` — SHA-256 checksums.

The committed golden fixture contains only normalized semantic behavior. Runtime
timestamps, durations, random IDs, filesystem paths, and environment details do
not affect the reproducibility hash. Secret-shaped keys and bearer/API-key
patterns are replaced with `[REDACTED]`. Verification supports schema versions
1 and 2, rejects malformed manifests, missing files, checksum mismatches, and
golden drift, and exits non-zero with a file-specific error.

The original golden result remains unchanged. The additive strict file has
checksums and acceptance checks in the same verifier. It records its profile
and limits, not timestamps, random approvals or host paths. Actual HTTP races,
durable restart/migration, failure/crash and workspace escape regressions are
separate tests; this file is not a substitute for them. Manifest Git SHA points
to the current checkout commit; results generated before commit include local
changes and must not be described as a clean released revision. Checksums detect
drift and do not authenticate authorship.

Native benchmark reports in `.tmp/` are separately labeled unavailable. Protocol
success is not native/model success. See [verification](portfolio-verification.md).

## Separate connected evidence bundle

Run the real-process browser suite before `python scripts/verify_connected_evidence.py`.
It writes `artifacts/portfolio/connected-evidence` with raw synthetic HTTP evidence,
checksums and a stable semantic summary. This records browser approval, direct
SQLite effect counts, duplicate rejection and process restart. Skill instructions
and hashes are inspected together; keyword consumption remains false. The original
golden fixture and generator are preserved. [Provenance and limits](portfolio-connected.md#reproduce-the-connected-proof)
explain the fault fixtures and what integrity verification establishes.
