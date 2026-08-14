#!/usr/bin/env python3
"""Check that the built wheel contains the vendored ARIA core."""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path


def main() -> int:
    wheels = sorted(Path("dist").glob("*.whl"))
    if not wheels:
        print("no wheel found in dist", file=sys.stderr)
        return 1
    with zipfile.ZipFile(wheels[-1]) as archive:
        names = set(archive.namelist())
    required = {
        "aria/internal/vendor_core/config.py",
        "aria/internal/vendor_core/tracing.py",
        "aria/internal/core/engine.py",
    }
    missing = sorted(required - names)
    if missing:
        print("wheel missing: " + ", ".join(missing), file=sys.stderr)
        return 1
    print(f"verified {wheels[-1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
