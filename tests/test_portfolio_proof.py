"""The published strict proof must measure effects and remain tamper evident."""

import json

from scripts.portfolio_demo import (
    _write_bundle,
    collect_evidence,
    collect_strict_evidence,
)
from scripts.verify_portfolio_evidence import verify


def test_strict_proof_is_repeatable_and_measures_effects():
    proof = collect_strict_evidence()
    assert proof == collect_strict_evidence()
    assert proof["profile"] == {"mode": "approval_gated", "safety": "block"}
    assert proof["authorized_effects"] == 1
    assert proof["duplicate_denied"] is True
    assert proof["denied_effects"] == 0
    assert set(proof["denials"]) == {
        "altered_arguments",
        "wrong_run",
        "rejected",
        "expired",
        "unknown_tool",
        "invalid_schema",
    }
    assert all(proof["denials"].values())
    assert proof["replay_effects"] == 0
    assert proof["replay_dry_run"] is True


def test_strict_proof_is_in_verified_bundle(tmp_path):
    _write_bundle(tmp_path, collect_evidence())
    assert verify(tmp_path) == []
    strict = tmp_path / "strict-profile.json"
    assert json.loads(strict.read_text())["authorized_effects"] == 1
    strict.write_text("{}")
    assert any("checksum mismatch" in error for error in verify(tmp_path))
