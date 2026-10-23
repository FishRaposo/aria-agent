"""The new evidence gate rejects tampering and checksummed false claims."""

import hashlib
import json

from aria.internal.evidence import reproducibility_hash, write_checksums, write_json
from scripts.verify_connected_evidence import verify


def bundle(directory):
    result = {
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
    body = "Synthetic verifier fixture only."
    observations = {
        "snapshot": {
            "catalog": [{}] * 5,
            "activated": [
                {
                    "name": "calculator",
                    "selection_method": "automatic",
                    "source": "builtin:calculator/SKILL.md",
                    "instructions": body,
                    "content_hash": hashlib.sha256(body.encode()).hexdigest(),
                }
            ],
            "context_report": {"context_consumed": False},
        },
        "completed": {
            "status": "completed",
            "execution_status": "completed",
            "result": "Task created: synthetic fixture",
        },
        "memory": {"messages": [{"content": "Task created: synthetic fixture"}]},
    }
    write_json(
        directory / "report.json",
        {"result": result, "reproducibility_hash": reproducibility_hash(result)},
    )
    write_json(directory / "observations.json", observations)
    seal(directory)


def seal(directory):
    report = json.loads((directory / "report.json").read_text())
    write_json(
        directory / "manifest.json",
        {
            "schema_version": 1,
            "reproducibility_hash": report["reproducibility_hash"],
            "files": write_checksums(directory, ["report.json", "observations.json"]),
        },
    )


def test_raw_observation_tampering_is_rejected(tmp_path):
    bundle(tmp_path)
    assert verify(tmp_path) == []
    (tmp_path / "observations.json").write_text("{}")
    assert "checksum mismatch: observations.json" in verify(tmp_path)


def test_resealed_false_effect_count_is_rejected(tmp_path):
    bundle(tmp_path)
    report = json.loads((tmp_path / "report.json").read_text())
    report["result"]["authorized_effects"] = 2
    report["reproducibility_hash"] = reproducibility_hash(report["result"])
    write_json(tmp_path / "report.json", report)
    seal(tmp_path)
    assert "connected workflow acceptance failed" in verify(tmp_path)


def test_resealed_body_change_cannot_reuse_historical_hash(tmp_path):
    bundle(tmp_path)
    observations = json.loads((tmp_path / "observations.json").read_text())
    observations["snapshot"]["activated"][0]["instructions"] = "Changed body"
    write_json(tmp_path / "observations.json", observations)
    seal(tmp_path)
    assert "invalid observed skill evidence" in verify(tmp_path)
