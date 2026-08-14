# Portfolio evidence

`make evidence` runs `scripts/portfolio_demo.py` and then
`scripts/verify_portfolio_evidence.py`. The ignored bundle contains:

- `manifest.json` — schema version, mode, Git SHA, suite/result/reproducibility hashes, and file digests;
- `report.json` — canonical redacted result;
- `report.md` — human-readable view;
- `checksums.sha256` — SHA-256 checksums.

The committed golden fixture contains only normalized semantic behavior. Runtime
timestamps, durations, random IDs, filesystem paths, and environment details do
not affect the reproducibility hash. Secret-shaped keys and bearer/API-key
patterns are replaced with `[REDACTED]`. Verification supports schema versions
1 and 2, rejects malformed manifests, missing files, checksum mismatches, and
golden drift, and exits non-zero with a file-specific error.
