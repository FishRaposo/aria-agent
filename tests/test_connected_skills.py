"""Saved skill evidence and credential-free application skill selection."""

import hashlib
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from aria.agents import AriaAgent
from aria.approvals import ApprovalGate
from aria.skills import SkillRegistry
from aria.store import InMemoryApprovalStore
from aria.tools import build_default_registry


@pytest.fixture
def copied_skill_root(tmp_path, monkeypatch):
    from aria import skill_runtime

    root = tmp_path / "skills"
    shutil.copytree(skill_runtime._source_root(), root)
    monkeypatch.setattr(skill_runtime, "_source_root", lambda: root)
    return root


@pytest.mark.parametrize(
    "query,name",
    [
        ("calculate 2+2", "calculator"),
        ("create a task to review", "task-creator"),
        ("draft email to team@example.com", "email-draft"),
        ("read notes.txt", "file-reader"),
        ("search routing", "web-search"),
    ],
)
def test_automatic_selection_is_relevant_and_explained(query, name):
    from aria.skill_runtime import create_api_skill_session

    session = create_api_skill_session()
    prepared = session.prepare_turn(query, [])
    bodies = prepared.report.to_dict()["loaded_instruction_bodies"]
    assert [body["name"] for body in bodies] == [name]
    assert bodies[0]["selection_method"] == "automatic"
    assert bodies[0]["selection_reason"]
    assert len(bodies[0]["content_hash"]) == 64
    assert bodies[0]["source"] == f"builtin:{name}/SKILL.md"
    assert prepared.report.to_dict()["context_consumed"] is False


def test_automatic_multistep_bounded_deduplicated_and_override():
    from aria.skill_runtime import create_api_skill_session

    session = create_api_skill_session(planning_mode="multi", max_steps=3)
    prepared = session.prepare_turn(
        "calculate 1+1; calculate 2+2; search birds; read notes.txt", []
    )
    assert [body["name"] for body in prepared.report.loaded_instruction_bodies] == [
        "calculator",
        "web-search",
    ]
    explicit = session.prepare_turn("/file-reader calculate 2+2", [])
    assert explicit.query == "calculate 2+2"
    assert [body["name"] for body in explicit.report.loaded_instruction_bodies] == [
        "file-reader"
    ]
    assert (
        explicit.report.loaded_instruction_bodies[0]["selection_method"] == "explicit"
    )
    assert (
        session.prepare_turn("hello there", []).report.loaded_instruction_bodies == ()
    )


def test_snapshot_metadata_only_and_historical_evidence():
    from aria.skill_runtime import build_skills_snapshot, create_api_skill_session

    empty = build_skills_snapshot(session_id="alpha", run=None)
    assert len(empty["catalog"]) == 5
    assert empty["activated"] == []
    assert all("instructions" not in entry for entry in empty["catalog"])
    assert empty["context_available"] is False
    session = create_api_skill_session()
    report = session.prepare_turn("calculate 1+2", []).report.to_dict()
    report["loaded_instruction_bodies"][0]["instructions"] = (
        "Historical instructions, preserved verbatim."
    )
    snapshot = build_skills_snapshot(
        session_id="alpha", run={"run_id": "run-1", "skill_context": report}
    )
    assert snapshot["run_id"] == "run-1"
    assert (
        snapshot["activated"][0]["instructions"]
        == "Historical instructions, preserved verbatim."
    )
    assert snapshot["activated"][0]["run_id"] == "run-1"
    assert snapshot["activated"][0]["scope"] == "builtin"
    legacy = build_skills_snapshot(
        session_id="alpha", run={"run_id": "old", "skill_context": None}
    )
    assert legacy["context_available"] is False
    assert legacy["activated"] == []


def test_distinct_run_sessions_never_share_activation():
    from aria.skill_runtime import create_api_skill_session

    first, second = create_api_skill_session(), create_api_skill_session()
    first.prepare_turn("calculate 1+2", [])
    second.prepare_turn("read notes.txt", [])
    assert [body["name"] for body in first.report().loaded_instruction_bodies] == [
        "calculator"
    ]
    assert [body["name"] for body in second.report().loaded_instruction_bodies] == [
        "file-reader"
    ]


def test_concurrent_sessions_keep_only_their_selected_content():
    from aria.skill_runtime import create_api_skill_session

    def prepare(query):
        return create_api_skill_session().prepare_turn(query, []).report.to_dict()

    with ThreadPoolExecutor(max_workers=2) as pool:
        reports = list(pool.map(prepare, ["calculate 2+3", "read notes.txt"]))
    assert [body["name"] for body in reports[0]["loaded_instruction_bodies"]] == [
        "calculator"
    ]
    assert [body["name"] for body in reports[1]["loaded_instruction_bodies"]] == [
        "file-reader"
    ]


def test_metadata_discovery_does_not_read_instruction_body(
    copied_skill_root, monkeypatch
):
    from aria.skill_runtime import build_skills_snapshot, create_api_skill_session

    def forbidden_read(*args, **kwargs):
        raise AssertionError("Metadata discovery read the whole skill")

    monkeypatch.setattr(Path, "read_text", forbidden_read)
    # A body that cannot decode must not prevent valid frontmatter discovery.
    path = copied_skill_root / "calculator" / "SKILL.md"
    path.write_bytes(
        b"---\nname: calculator\ndescription: Arithmetic.\n---\n"
        + b"x" * 20000
        + b"\xff"
    )
    assert len(build_skills_snapshot(session_id="a", run=None)["catalog"]) == 5
    session = create_api_skill_session()
    with pytest.raises(ValueError, match="safely"):
        session.prepare_turn("calculate 2+3", [])


@pytest.mark.parametrize(
    "damage", ["missing", "malformed", "empty", "identity", "oversize"]
)
def test_invalid_selected_skill_blocks_before_any_tool_effect(
    copied_skill_root, damage
):
    from aria.skill_runtime import create_api_skill_session

    session = create_api_skill_session()
    source = copied_skill_root / "calculator" / "SKILL.md"
    if damage == "missing":
        source.unlink()
    elif damage == "malformed":
        source.write_text("not a skill", encoding="utf-8")
    elif damage == "empty":
        source.write_text(
            "---\nname: calculator\ndescription: Arithmetic.\n---\n", encoding="utf-8"
        )
    elif damage == "identity":
        source.write_text(
            "---\nname: wrong-name\ndescription: Arithmetic.\n---\nDo it.",
            encoding="utf-8",
        )
    else:
        source.write_text(
            "---\nname: calculator\ndescription: Arithmetic.\n---\n" + "x" * 40000,
            encoding="utf-8",
        )
    registry = build_default_registry()
    invoked = []
    registry.tools["calculator"] = lambda **arguments: (
        invoked.append(arguments) or "unexpected"
    )
    agent = AriaAgent(
        registry, ApprovalGate(mode="free_running"), skill_session=session
    )
    result = agent.run_structured("calculate 2+2")
    assert result.status == "blocked"
    assert invoked == []
    assert result.skill_context["context_consumed"] is False
    assert any(
        entry.get("name") == "skill_loading_denied" for entry in result.trace["entries"]
    )


def test_hash_and_saved_body_stay_immutable_when_current_source_changes(
    copied_skill_root,
):
    from aria.skill_runtime import build_skills_snapshot, create_api_skill_session

    report = (
        create_api_skill_session().prepare_turn("calculate 1+2", []).report.to_dict()
    )
    body = report["loaded_instruction_bodies"][0]
    assert (
        body["content_hash"]
        == hashlib.sha256(body["instructions"].encode()).hexdigest()
    )
    source = copied_skill_root / "calculator" / "SKILL.md"
    source.write_text(
        "---\nname: calculator\ndescription: Changed description.\n---\nChanged body.",
        encoding="utf-8",
    )
    snapshot = build_skills_snapshot(
        session_id="a", run={"run_id": "old", "skill_context": report}
    )
    assert snapshot["activated"][0]["instructions"] == body["instructions"]
    assert snapshot["activated"][0]["content_hash"] == body["content_hash"]
    assert snapshot["catalog"][0]["description"] == "Changed description."
    snapshot["activated"][0]["instructions"] = "Mutated projection"
    assert (
        report["loaded_instruction_bodies"][0]["instructions"] == body["instructions"]
    )


def test_selected_skill_source_resolved_escape_fails_closed(
    copied_skill_root, tmp_path, monkeypatch
):
    from aria.skill_runtime import create_api_skill_session

    session = create_api_skill_session()
    outside = tmp_path / "outside-skill.md"
    outside.write_text(
        "---\nname: calculator\ndescription: Outside.\n---\nOutside instructions.",
        encoding="utf-8",
    )
    original_resolve = Path.resolve

    def escaped(path, *args, **kwargs):
        if path == copied_skill_root / "calculator" / "SKILL.md":
            return outside
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", escaped)
    with pytest.raises(ValueError, match="safely"):
        session.prepare_turn("calculate 1+2", [])


def test_unresolvable_selected_skill_returns_blocked_run(
    copied_skill_root, monkeypatch
):
    from aria.skill_runtime import create_api_skill_session

    session = create_api_skill_session()
    original_resolve = Path.resolve

    def looping(path, *args, **kwargs):
        if path == copied_skill_root / "calculator" / "SKILL.md":
            raise RuntimeError("Symlink loop")
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", looping)
    agent = AriaAgent(
        build_default_registry(),
        ApprovalGate(mode="free_running"),
        skill_session=session,
    )
    result = agent.run_structured("calculate 1+2")
    assert result.status == "blocked"
    assert not any(
        entry.get("type") == "tool_call" for entry in result.trace["entries"]
    )


def test_strict_file_escape_is_blocked_before_tool_invocation(tmp_path, monkeypatch):
    monkeypatch.setenv("ARIA_SANDBOX_DIR", str(tmp_path))
    registry = build_default_registry()
    invoked = []
    original = registry.tools["file_reader"]
    registry.tools["file_reader"] = lambda **arguments: (
        invoked.append(arguments) or original(**arguments)
    )
    agent = AriaAgent(
        registry,
        ApprovalGate(mode="approval_gated", store=InMemoryApprovalStore()),
        safety_mode="block",
    )
    result = agent.run_structured("read ../outside.txt")
    assert result.status == "blocked"
    assert invoked == []


def test_library_sessions_remain_explicit(tmp_path):
    directory = tmp_path / ".agents" / "skills" / "calculator"
    directory.mkdir(parents=True)
    (directory / "SKILL.md").write_text(
        "---\nname: calculator\ndescription: Arithmetic.\n---\nCalculate.",
        encoding="utf-8",
    )
    session = SkillRegistry.discover(user_root=tmp_path).create_session()
    assert (
        session.prepare_turn("calculate 2+2", []).report.loaded_instruction_bodies == ()
    )
