"""Sandboxed file reader tool.

Reads a text file but only from within an allowlisted sandbox directory. The
resolved absolute path is verified to live inside the sandbox root, so
path-traversal payloads (``../../etc/passwd``), absolute paths outside the
sandbox, and symlink escapes are all rejected. This is a ``safe`` permission-
level tool because it can only ever read inside the sandbox.

The sandbox root defaults to ``<project>/sandbox`` and can be overridden via the
``ARIA_SANDBOX_DIR`` environment variable.
"""

import os
from pathlib import Path

from pydantic import BaseModel, Field

_MAX_BYTES = 4000


def get_sandbox_root() -> Path:
    """Return the resolved sandbox root, creating it if necessary."""
    env = os.environ.get("ARIA_SANDBOX_DIR")
    if env:
        root = Path(env)
    else:
        # <repo>/src/aria/builtin_tools/file_reader.py -> <repo>/sandbox
        root = Path(__file__).resolve().parents[3] / "sandbox"
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


class FileReaderInput(BaseModel):
    filepath: str = Field(
        description="Path to a file, relative to the sandbox directory"
    )


def _resolve_within_sandbox(filepath: str) -> Path:
    """Resolve ``filepath`` against the sandbox and ensure it stays inside it.

    Raises ``PermissionError`` if the resolved path escapes the sandbox root.
    """
    root = get_sandbox_root()
    # Reject absolute paths outright — everything must be sandbox-relative.
    candidate = (root / filepath).resolve()
    # ``Path.is_relative_to`` (3.9+) gives us a robust containment check that
    # also defeats ``..`` traversal and absolute-path injection.
    if candidate != root and not candidate.is_relative_to(root):
        raise PermissionError("Path escapes the sandbox directory")
    return candidate


def file_reader(filepath: str) -> str:
    """Read up to ``_MAX_BYTES`` chars from a sandboxed file path."""
    try:
        target = _resolve_within_sandbox(filepath)
    except PermissionError as exc:
        return f"Error: access denied — {exc}"
    except (ValueError, OSError) as exc:
        return f"Error resolving path: {exc}"

    if not target.exists():
        return f"Error: File not found at '{filepath}' (sandbox-relative)"
    if not target.is_file():
        return f"Error: '{filepath}' is not a regular file"

    try:
        content = target.read_text(encoding="utf-8")[:_MAX_BYTES]
    except PermissionError:
        return f"Error: Permission denied for '{filepath}'"
    except UnicodeDecodeError:
        return f"Error: '{filepath}' is not a UTF-8 text file"
    except OSError as exc:
        return f"Error reading file: {exc}"

    return f"File contents (first {_MAX_BYTES} chars):\n{content}"
