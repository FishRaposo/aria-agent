# Changelog

## 2026-08-14 — comprehensive local-core finalization

- Vendored the pinned server compatibility subset and removed the archived
  sibling-package installation path.
- Added bounded multi-hop planning, deterministic safety, safe-tool retries,
  fixed-window rate limits, ordered SSE events, dry-run replay, local memory
  search, and an optional approval sweeper.
- Added a redacted, checksummed offline evidence bundle with a golden fixture.
- Aligned packaging, wheel checks, CI, dashboard lint/build/browser gates, docs,
  public catalog copy, and MIT attribution.
- Recorded the finalization verification snapshot: 200 Python tests, 12 focused
  skill tests, Ruff check plus 72 format-clean files, and Pyright with 0 errors.
