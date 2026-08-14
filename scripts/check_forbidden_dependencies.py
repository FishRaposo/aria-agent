#!/usr/bin/env python3
"""Fail when an archived sibling shared-core dependency reappears."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = (
    re.compile(r"\.\./shared-core"),
    re.compile(r"git\+https://.*operator-shared-core"),
    re.compile(r"(?:from|import)\s+shared_core"),
)
SKIP_PARTS = {".git", "node_modules", ".pytest_cache", ".ruff_cache", "artifacts"}


def main() -> int:
    failures: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in SKIP_PARTS for part in path.parts):
            continue
        if path.suffix.lower() not in {
            ".py",
            ".md",
            ".yml",
            ".yaml",
            ".toml",
            ".txt",
            ".json",
            "",
            ".js",
            ".ts",
            ".tsx",
        }:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for pattern in PATTERNS:
            if pattern.search(text):
                failures.append(f"{path.relative_to(ROOT)}: {pattern.pattern}")
    if failures:
        print("forbidden external dependency references:", file=sys.stderr)
        print("\n".join(failures), file=sys.stderr)
        return 1
    print("no forbidden external dependency references")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
