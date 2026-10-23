"""Offline tests exercise real hook processes; they are not native model trials."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "coding_agent_setup"


def module(name):
    path = EXAMPLE / f"{name}.py"
    assert path.is_file(), f"Native setup contract implementation missing: {name}"
    spec = importlib.util.spec_from_file_location(f"native_{name}", path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


@pytest.fixture
def fixture_repo(tmp_path):
    root = tmp_path / "fixture"
    module("setup").install(root, profile="configured", task_id="B01")
    return root


def hook(root, payload):
    return subprocess.run(
        [sys.executable, str(root / ".aria" / "guard.py")],
        input=payload if isinstance(payload, str) else json.dumps(payload),
        text=True,
        capture_output=True,
        timeout=5,
        cwd=root,
    )


def event(root, tool="Read", path="app.py"):
    return {
        "hook_event_name": "PreToolUse",
        "cwd": str(root),
        "tool_name": tool,
        "tool_input": {"file_path": str(root / path)},
    }


@pytest.mark.parametrize("payload", ["not json", "[]", "null", "{}"])
def test_malformed_input_is_blocking(fixture_repo, payload):
    result = hook(fixture_repo, payload)
    assert result.returncode == 2
    assert result.stderr


def test_guard_leaves_normal_permission_flow_for_scoped_tool(fixture_repo):
    result = hook(fixture_repo, event(fixture_repo, "Edit"))
    assert result.returncode == 0
    assert result.stdout == ""


@pytest.mark.parametrize(
    "path",
    [
        ".secrets.txt",
        "../escape.txt",
        "notes/../app.py",
        ".aria/guard.py",
        ".claude/settings.json",
    ],
)
def test_protected_traversal_paths_cannot_create_side_effect(fixture_repo, path):
    before = (fixture_repo / ".secrets.txt").read_bytes()
    result = hook(fixture_repo, event(fixture_repo, "Write", path))
    assert result.returncode == 2
    assert (fixture_repo / ".secrets.txt").read_bytes() == before
    assert not (fixture_repo.parent / "escape.txt").exists()


def test_unknown_tools_and_changed_cwd_are_denied(fixture_repo):
    payload = event(fixture_repo)
    payload["tool_name"] = "mcp__mail__send"
    assert hook(fixture_repo, payload).returncode == 2
    payload = event(fixture_repo)
    payload["cwd"] = str(fixture_repo.parent)
    assert hook(fixture_repo, payload).returncode == 2


def test_symlink_guard_with_mocked_filesystem():
    guard = module("guard")
    from unittest.mock import patch

    root = Path.cwd().resolve()
    with patch.object(Path, "is_symlink", lambda self: self.name == "linked"):
        with pytest.raises(ValueError, match="link"):
            guard.safe_path(root, str(root / "linked" / "app.py"))


def test_real_symlink_escape_when_host_supports_it(fixture_repo, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    link = fixture_repo / "linked"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"Host cannot create symlink; mocked rejection still tested: {exc}")
    assert (
        hook(fixture_repo, event(fixture_repo, "Write", "linked/pwn.txt")).returncode
        == 2
    )
    assert not (outside / "pwn.txt").exists()


def test_stop_cannot_claim_verification_for_broken_code(fixture_repo):
    payload = {
        "hook_event_name": "Stop",
        "cwd": str(fixture_repo),
        "stop_hook_active": False,
    }
    result = hook(fixture_repo, payload)
    assert result.returncode == 2
    assert "verification" in result.stderr.lower()
    source = (fixture_repo / "app.py").read_text()
    (fixture_repo / "app.py").write_text(
        source.replace("return a - b", "return a + b", 1)
    )
    assert hook(fixture_repo, payload).returncode == 0
    audit = [
        json.loads(line)
        for line in (fixture_repo / ".aria/audit.jsonl").read_text().splitlines()
    ]
    assert audit[-1]["verification"] == "passed"


def test_continued_stop_failure_remains_failed_and_does_not_loop(fixture_repo):
    payload = {
        "hook_event_name": "Stop",
        "cwd": str(fixture_repo),
        "stop_hook_active": True,
    }
    result = hook(fixture_repo, payload)
    assert result.returncode == 0
    audit = [
        json.loads(line)
        for line in (fixture_repo / ".aria/audit.jsonl").read_text().splitlines()
    ]
    assert audit[-1]["verification"] == "failed"


def test_verifier_never_executes_modified_fixture_code(fixture_repo):
    marker = fixture_repo / "pwned.txt"
    (fixture_repo / "app.py").write_text(f"open({str(marker)!r}, 'w').write('bad')")
    result = module("verify").verify(fixture_repo, "B01")
    assert not result["passed"]
    assert not marker.exists()


def test_installed_hook_failures_and_timeouts_are_fail_closed(fixture_repo):
    settings = json.loads((fixture_repo / ".claude/settings.json").read_text())
    handler = settings["hooks"]["PreToolUse"][0]["hooks"][0]
    assert handler["onFailure"] == "block"
    assert handler["timeout"] > 0
    assert handler["args"] == [str(fixture_repo / ".aria/guard.py")]
    assert handler["command"] == sys.executable
    assert settings["hooks"]["PreToolUse"][0]["matcher"] == "*"
    assert not handler.get("async", False)


@pytest.mark.parametrize("kind", ["crash", "timeout", "malformed"])
def test_protocol_supervisor_blocks_guard_failure(tmp_path, kind):
    guard_script = tmp_path / "guard.py"
    contents = {
        "crash": "raise RuntimeError('synthetic crash')",
        "timeout": "import time; time.sleep(5)",
        "malformed": "print('{broken')",
    }
    guard_script.write_text(contents[kind])
    result = module("benchmark").probe_hook(guard_script, {}, timeout=0.1)
    assert result["blocked"] is True
    assert result["status"] == kind


def test_skills_are_canonical_imports_not_private_copies(fixture_repo):
    assert (fixture_repo / ".agents/skills/scoped-repair/SKILL.md").is_file()
    assert (
        "@.agents/skills/scoped-repair/SKILL.md"
        in (fixture_repo / "CLAUDE.md").read_text()
    )
    assert not (fixture_repo / ".claude/skills").exists()


def test_setup_refuses_existing_target_and_uninstall_preserves_edits(fixture_repo):
    setup = module("setup")
    with pytest.raises(FileExistsError):
        setup.install(fixture_repo, profile="baseline", task_id="B01")
    source = fixture_repo / "app.py"
    source.write_text("owner edit\n")
    setup.uninstall(fixture_repo)
    assert source.read_text() == "owner edit\n"
    assert not (fixture_repo / ".claude/settings.json").exists()


def test_uninstall_refuses_changed_control_files_atomically(fixture_repo):
    (fixture_repo / "CLAUDE.md").write_text("owner instructions")
    with pytest.raises(ValueError, match="modified"):
        module("setup").uninstall(fixture_repo)
    assert (fixture_repo / ".claude/settings.json").exists()


@pytest.mark.parametrize("kind", ["directory", "symlink", "reparse"])
def test_uninstall_preflights_audit_before_removing_any_control(
    fixture_repo, tmp_path, kind
):
    from types import SimpleNamespace
    from unittest.mock import patch

    setup = module("setup")
    audit = fixture_repo / ".aria/audit.jsonl"
    source = fixture_repo / "app.py"
    source.write_text("owner source edit\n")
    if kind == "directory":
        audit.mkdir()
    else:
        audit.write_text("owner audit\n")
    outside = tmp_path / "outside-owner.txt"
    outside.write_text("outside owner data\n")
    watched = [
        *(fixture_repo / name for name in setup.CONTROL_FILES),
        fixture_repo / ".aria/install.json",
        source,
        outside,
    ]
    before = {path: path.read_bytes() for path in watched}
    original_symlink = Path.is_symlink
    original_lstat = Path.lstat

    def is_symlink(path):
        return (kind == "symlink" and path == audit) or original_symlink(path)

    def lstat(path, *args, **kwargs):
        if kind == "reparse" and path == audit:
            return SimpleNamespace(
                st_file_attributes=0x400,
                st_mode=original_lstat(path, *args, **kwargs).st_mode,
            )
        return original_lstat(path, *args, **kwargs)

    with (
        patch.object(Path, "is_symlink", is_symlink),
        patch.object(Path, "lstat", lstat),
    ):
        with pytest.raises((ValueError, OSError)):
            setup.uninstall(fixture_repo)
    for path, contents in before.items():
        assert path.is_file(), f"Preflight failure removed {path.name}"
        assert path.read_bytes() == contents
    assert audit.exists()


def test_uninstall_removes_regular_audit_and_preserves_source(fixture_repo):
    audit = fixture_repo / ".aria/audit.jsonl"
    audit.write_text('{"event":"fixture"}\n')
    source = fixture_repo / "app.py"
    before = source.read_bytes()
    module("setup").uninstall(fixture_repo)
    assert not audit.exists()
    assert not (fixture_repo / ".aria/install.json").exists()
    assert source.read_bytes() == before


def test_fixed_benchmark_retains_all_unavailable_native_cells(tmp_path):
    from unittest.mock import patch

    benchmark = module("benchmark")
    with patch.object(
        benchmark.subprocess,
        "run",
        side_effect=AssertionError("no CLI calls permitted"),
    ):
        report = benchmark.run(tmp_path / "report")
    assert len(report["rows"]) == 60
    assert len({row["task_id"] for row in report["rows"]}) == 10
    assert sum(task["category"] == "benign" for task in benchmark.tasks()) == 5
    assert {row["profile"] for row in report["rows"]} == {"baseline", "configured"}
    assert {row["trial"] for row in report["rows"]} == {1, 2, 3}
    assert all(row["status"] == "unavailable" for row in report["rows"])
    assert all(
        row["cost_usd"] is None and row["verification"] == "not_run"
        for row in report["rows"]
    )
    assert report["native_runs"] == 0
    assert report["improvement"] is None
    assert report["task_sha256"]
    assert (tmp_path / "report/report.json").exists()


def test_native_execution_requires_budget_model_and_isolation(tmp_path):
    with pytest.raises(ValueError, match="budget"):
        module("benchmark").run(tmp_path / "report", execute_native=True)


def test_baseline_does_not_install_configured_hooks_or_import(tmp_path):
    root = tmp_path / "baseline"
    module("setup").install(root, profile="baseline", task_id="B01")
    settings = json.loads((root / ".claude/settings.json").read_text())
    assert "hooks" not in settings
    assert "@.agents" not in (root / "CLAUDE.md").read_text()


def test_untrusted_contract_cannot_expand_verifier_file_access(fixture_repo):
    app = fixture_repo / "app.py"
    app.write_text(app.read_text().replace("return a - b", "return a + b", 1))
    path = fixture_repo / ".aria/contract.json"
    contract = json.loads(path.read_text())
    contract["protected_contents"]["../outside.txt"] = "outside"
    path.write_text(json.dumps(contract))
    result = module("verify").verify(fixture_repo, "B01")
    assert result["passed"] is False
    assert "contract path" in result["reason"]


def test_native_runner_preserves_failed_verification_and_raw_events(
    fixture_repo, tmp_path
):
    from unittest.mock import patch

    benchmark = module("benchmark")
    task = next(item for item in benchmark.tasks() if item["id"] == "N05")
    root = tmp_path / "native-cell"

    def fake_native(command, **kwargs):
        app = root / "app.py"
        app.write_text(app.read_text().replace("return a - b", "return a + b", 1))
        events = json.dumps(
            {"type": "result", "subtype": "success", "total_cost_usd": 0.02}
        )
        return subprocess.CompletedProcess(command, 0, events, "")

    with patch.object(benchmark.subprocess, "run", fake_native):
        row = benchmark.native_row(
            root, task, "baseline", "fixture-model", 0.10, "mock-cli", 10
        )
    assert row["status"] == "failed"
    assert row["external_verification"]["passed"] is True
    assert row["hook_verification"] == "not_observed"
    assert row["cost_usd"] == 0.02
    assert (Path(row["raw_artifacts"]) / "stdout.jsonl").is_file()
