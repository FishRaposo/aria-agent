"""Deterministic evidence contracts for the offline portfolio demo."""

import shutil
from pathlib import Path

from aria.internal.evidence import (
    canonical_json,
    redact_secrets,
    reproducibility_hash,
)
from scripts.portfolio_demo import _write_bundle, collect_evidence
from scripts.verify_portfolio_evidence import verify


def test_canonical_json_sorts_keys_and_is_stable():
    assert canonical_json({"b": 2, "a": 1}) == '{"a":1,"b":2}'


def test_reproducibility_hash_excludes_runtime_fields():
    first = {"value": 3, "created_at": 1, "duration_ms": 10}
    second = {"duration_ms": 999, "created_at": 42, "value": 3}
    assert reproducibility_hash(first) == reproducibility_hash(second)


def test_redaction_removes_common_secret_shapes():
    redacted = redact_secrets(
        {
            "api_key": "sk-secret",
            "authorization": "Bearer token",
            "nested": {"password": "pw", "safe": "ok"},
        }
    )
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["authorization"] == "[REDACTED]"
    assert redacted["nested"]["password"] == "[REDACTED]"
    assert redacted["nested"]["safe"] == "ok"


def test_tampering_and_missing_files_fail_verification(tmp_path: Path):
    source = tmp_path / "source"
    _write_bundle(source, collect_evidence())
    bundle = tmp_path / "bundle"
    shutil.copytree(source, bundle)
    (bundle / "report.md").write_text("tampered", encoding="utf-8")
    errors = verify(bundle)
    assert any("checksum mismatch" in error for error in errors)
    (bundle / "report.md").unlink()
    assert any("missing file" in error for error in verify(bundle))


def test_malformed_manifest_fails_verification(tmp_path: Path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "manifest.json").write_text("not-json", encoding="utf-8")
    assert any("malformed manifest" in error for error in verify(bundle))
