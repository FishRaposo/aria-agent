#!/usr/bin/env python3
"""Verify the separate, real-process connected-workflow evidence bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from scripts.verify_portfolio_evidence import verify as verify_bundle  # noqa: E402


def verify(directory: Path) -> list[str]:
    errors = verify_bundle(directory)
    if errors:
        return errors
    try:
        result = json.loads((directory / "report.json").read_text(encoding="utf-8"))[
            "result"
        ]
        expected = {
            "catalog_count": 5,
            "automatic_skill": "calculator",
            "context_consumed": False,
            "authorized_effects": 1,
            "duplicate_status": 409,
            "restart_preserved": True,
            "memory_outcomes": 1,
            "session_isolated": True,
            "routing": "keyword",
            "persistence": "sqlite",
        }
        if result != expected:
            errors.append("connected workflow acceptance failed")
        observations = json.loads(
            (directory / "observations.json").read_text(encoding="utf-8")
        )
        snapshot = observations["snapshot"]
        selected = snapshot["activated"]
        if len(snapshot["catalog"]) != 5 or len(selected) != 1:
            errors.append("unexpected observed skill selection")
        for skill in selected:
            if (
                skill["name"] != "calculator"
                or skill["selection_method"] != "automatic"
                or not skill["source"].startswith("builtin:")
                or hashlib.sha256(skill["instructions"].encode()).hexdigest()
                != skill["content_hash"]
            ):
                errors.append("invalid observed skill evidence")
        if snapshot["context_report"]["context_consumed"] is not False:
            errors.append("keyword context consumption must remain false")
        completed = observations["completed"]
        if (
            completed["status"] != "completed"
            or completed["execution_status"] != "completed"
            or "Task created" not in completed["result"]
        ):
            errors.append("invalid observed execution outcome")
        outcomes = [
            message
            for message in observations["memory"]["messages"]
            if "Task created" in message["content"]
        ]
        if len(outcomes) != 1:
            errors.append("conversation outcome is not unique")
    except (OSError, ValueError, KeyError, TypeError):
        errors.append("malformed connected observations")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "directory",
        nargs="?",
        type=Path,
        default=ROOT / "artifacts/portfolio/connected-evidence",
    )
    errors = verify(parser.parse_args().directory)
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    if not errors:
        print("verified connected HTTP/browser/SQLite evidence")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
