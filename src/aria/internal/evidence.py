"""Small, dependency-free helpers for reproducible ARIA evidence bundles.

The evidence format is intentionally boring: UTF-8 JSON, SHA-256 checksums,
and a manifest that names the files and the normalized result hash.  Runtime
fields are excluded only from the reproducibility hash; the raw report remains
available for inspection.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

SCHEMA_VERSION = 1
REDACTED = "[REDACTED]"
_RUNTIME_KEYS = {
    "created_at",
    "updated_at",
    "timestamp",
    "timestamps",
    "started_at",
    "finished_at",
    "duration",
    "duration_ms",
    "latency",
    "latency_ms",
    "start_ms",
    "end_ms",
    "wall_clock_ms",
    "run_id",
    "trace_id",
    "span_id",
    "parent_span_id",
    "request_id",
    "generated_id",
    "path",
    "filesystem_path",
    "environment",
}
_SECRET_KEYS = {
    "api_key",
    "apikey",
    "access_token",
    "auth_token",
    "authorization",
    "client_secret",
    "password",
    "private_key",
    "refresh_token",
    "secret",
    "token",
}
_SECRET_PATTERN = re.compile(
    r"(?i)(bearer\s+|sk-[a-z0-9_-]{4,}|api[_-]?key\s*[=:]\s*)[^\s,;]+"
)


def canonical_json(value: Any) -> str:
    """Serialize JSON deterministically without insignificant whitespace."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _normalize_runtime(value: Any, *, key: str | None = None) -> Any:
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            child_key = str(raw_key)
            if child_key.lower() in _RUNTIME_KEYS:
                continue
            normalized[child_key] = _normalize_runtime(raw_value, key=child_key)
        return normalized
    if isinstance(value, list):
        return [_normalize_runtime(item) for item in value]
    if isinstance(value, tuple):
        return [_normalize_runtime(item) for item in value]
    return value


def reproducibility_hash(value: Any) -> str:
    """Hash a normalized result while ignoring non-deterministic runtime data."""

    normalized = _normalize_runtime(copy.deepcopy(value))
    return hashlib.sha256(canonical_json(normalized).encode("utf-8")).hexdigest()


def redact_secrets(value: Any, *, key: str | None = None) -> Any:
    """Return a deep-redacted copy suitable for writing to a public artifact."""

    if key is not None and key.lower() in _SECRET_KEYS:
        return REDACTED
    if isinstance(value, Mapping):
        return {
            str(child_key): redact_secrets(child_value, key=str(child_key))
            for child_key, child_value in value.items()
        }
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    if isinstance(value, tuple):
        return [redact_secrets(item) for item in value]
    if isinstance(value, str):
        return _SECRET_PATTERN.sub(lambda match: f"{match.group(1)}{REDACTED}", value)
    return value


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def write_json(path: Path, value: Any) -> None:
    path.write_text(canonical_json(value) + "\n", encoding="utf-8")


def write_checksums(directory: Path, filenames: list[str]) -> dict[str, str]:
    checksums = {name: sha256_file(directory / name) for name in sorted(filenames)}
    (directory / "checksums.sha256").write_text(
        "".join(f"{digest}  {name}\n" for name, digest in checksums.items()),
        encoding="utf-8",
    )
    return checksums


def verify_checksums(directory: Path, manifest: Mapping[str, Any]) -> list[str]:
    """Return clear verification errors rather than raising for user tooling."""

    errors: list[str] = []
    checksums_path = directory / "checksums.sha256"
    if not checksums_path.is_file():
        return ["missing checksums.sha256"]
    expected = dict(manifest.get("files", {}))
    checksum_lines: dict[str, str] = {}
    for line in checksums_path.read_text(encoding="utf-8").splitlines():
        parts = line.split("  ", 1)
        if len(parts) == 2 and parts[0] and parts[1]:
            checksum_lines[parts[1]] = parts[0]
    if not checksum_lines:
        errors.append("malformed checksums.sha256")
    for name, digest in checksum_lines.items():
        path = directory / name
        if not path.is_file():
            errors.append(f"missing file listed in checksums: {name}")
        elif sha256_file(path) != digest:
            errors.append(f"checksum mismatch: {name}")
    for name, digest in expected.items():
        path = directory / name
        if not path.is_file():
            errors.append(f"missing file: {name}")
            continue
        actual = sha256_file(path)
        if actual != digest:
            errors.append(f"checksum mismatch: {name}")
        if checksum_lines.get(name) != digest:
            errors.append(f"manifest/checksum disagreement: {name}")
    return errors
