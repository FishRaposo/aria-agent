#!/usr/bin/env python3
"""Verify an ARIA evidence bundle and its committed golden result."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aria.internal.evidence import (  # noqa: E402
    canonical_json,
    reproducibility_hash,
    verify_checksums,
)


def verify(directory: Path, golden: Path | None = None) -> list[str]:
    errors: list[str] = []
    manifest_path = directory / "manifest.json"
    report_path = directory / "report.json"
    if not manifest_path.is_file():
        return ["missing manifest.json"]
    if not report_path.is_file():
        errors.append("missing report.json")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"malformed manifest.json: {exc}"]
    if not isinstance(manifest, dict):
        errors.append("malformed manifest.json: expected object")
        return errors
    if manifest.get("schema_version") not in {1, 2}:
        errors.append("unsupported evidence schema version")
    errors.extend(verify_checksums(directory, manifest))
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"malformed report.json: {exc}")
        return errors
    if not isinstance(report, dict) or not isinstance(report.get("result"), dict):
        errors.append("malformed report.json: missing result object")
        return errors
    result = report["result"]
    expected_hash = manifest.get("reproducibility_hash")
    if expected_hash != reproducibility_hash(result):
        errors.append("reproducibility hash mismatch")
    if report.get("reproducibility_hash") != expected_hash:
        errors.append("manifest/report reproducibility hash disagreement")
    if golden is not None:
        if not golden.is_file():
            errors.append(f"missing golden fixture: {golden}")
        else:
            try:
                expected = json.loads(golden.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                errors.append(f"malformed golden fixture: {exc}")
            else:
                if canonical_json(result) != canonical_json(expected):
                    errors.append("golden fixture mismatch")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "directory",
        nargs="?",
        type=Path,
        default=ROOT / "artifacts/portfolio/aria-agent-evidence",
    )
    args = parser.parse_args()
    errors = verify(
        args.directory, ROOT / "tests/fixtures/golden/portfolio-evidence.json"
    )
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"verified {args.directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
