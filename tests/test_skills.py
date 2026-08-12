"""Offline contract tests for ARIA's progressive-disclosure skill layer."""

import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from aria.skills import SkillRegistry, SkillValidationError, parse_skill_markdown


def _skill_text(
    name: str,
    description: str | None = "A useful skill.",
    body: str = "# Instructions\n\nDo the useful thing.",
    compatibility: str | None = None,
) -> str:
    fields = [f"name: {name}"]
    if description is not None:
        fields.append(f"description: {description}")
    if compatibility is not None:
        fields.append(f"compatibility: {compatibility}")
    frontmatter = "\n".join(fields)
    return f"---\n{frontmatter}\n---\n\n{body}\n"


def _write_skill(
    root: Path,
    name: str,
    *,
    description: str = "A useful skill.",
    body: str = "# Instructions\n\nDo the useful thing.",
    compatibility: str | None = None,
    skill_dir: str = ".skills",
) -> Path:
    directory = root / skill_dir / name
    directory.mkdir(parents=True)
    (directory / "SKILL.md").write_text(
        _skill_text(name, description, body, compatibility), encoding="utf-8"
    )
    return directory


@pytest.fixture
def workspace_tmp_root() -> Path:
    root = Path(__file__).resolve().parents[1] / ".pytest-tmp"
    root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="skills-", dir=root) as directory:
        yield Path(directory)
    try:
        root.rmdir()
    except OSError:
        pass


def test_parse_skill_markdown_validates_required_frontmatter() -> None:
    document = parse_skill_markdown(
        _skill_text("release-notes", "Create concise release notes.")
    )
    assert document.name == "release-notes"
    assert document.description == "Create concise release notes."
    assert document.instructions.startswith("# Instructions")

    with pytest.raises(SkillValidationError, match="name"):
        parse_skill_markdown("---\ndescription: Missing a name.\n---\nbody")
    with pytest.raises(SkillValidationError, match="description"):
        parse_skill_markdown(_skill_text("release-notes", description=None))


def test_discovery_exposes_metadata_and_eager_hints_without_instructions(
    workspace_tmp_root: Path,
) -> None:
    body = """# When to Use

Use for tagged releases.

# Instructions

SECRET LEVEL TWO BODY
"""
    _write_skill(
        workspace_tmp_root,
        "release-notes",
        description="Create release notes.",
        body=body,
        compatibility="Requires a Git checkout.",
    )
    registry = SkillRegistry.discover(user_root=workspace_tmp_root)

    # Discovery is metadata-only. A hint changed after discovery must be the one
    # observed by the explicit eager catalogue read, never a cached body read.
    source = workspace_tmp_root / ".skills" / "release-notes" / "SKILL.md"
    source.write_text(
        _skill_text(
            "release-notes",
            "Create release notes.",
            "# When to Use\n\nUse for signed tagged releases.\n\n"
            "# Instructions\n\nNEW SECRET LEVEL TWO BODY",
            "Requires a Git checkout.",
        ),
        encoding="utf-8",
    )

    level_one = registry.catalog()
    assert level_one == (
        {
            "name": "release-notes",
            "description": "Create release notes.",
            "scope": "user",
            "source": str(
                workspace_tmp_root / ".skills" / "release-notes" / "SKILL.md"
            ),
        },
    )
    assert "SECRET LEVEL TWO BODY" not in repr(level_one)

    eager = registry.catalog(eager=True)
    assert eager[0]["activation_hints"] == (
        "Compatibility: Requires a Git checkout.\nUse for signed tagged releases."
    )
    assert "SECRET LEVEL TWO BODY" not in repr(eager)


def test_scope_precedence_is_project_then_user_then_builtin_and_project_is_opt_in(
    workspace_tmp_root: Path,
) -> None:
    project = workspace_tmp_root / "project"
    user = workspace_tmp_root / "user"
    builtin = workspace_tmp_root / "builtin"
    _write_skill(project, "shared", description="project copy")
    _write_skill(user, "shared", description="user copy")
    _write_skill(user, "user-only", description="user only")
    _write_skill(builtin, "shared", description="built-in copy")
    _write_skill(builtin, "builtin-only", description="built-in only")

    untrusted = SkillRegistry.discover(
        project_root=project,
        user_root=user,
        builtin_root=builtin,
        trust_project=False,
    )
    assert [(skill.name, skill.description, skill.scope) for skill in untrusted] == [
        ("shared", "user copy", "user"),
        ("user-only", "user only", "user"),
        ("builtin-only", "built-in only", "built-in"),
    ]

    trusted = SkillRegistry.discover(
        project_root=project,
        user_root=user,
        builtin_root=builtin,
        trust_project=True,
    )
    assert [(skill.name, skill.description, skill.scope) for skill in trusted] == [
        ("shared", "project copy", "project"),
        ("user-only", "user only", "user"),
        ("builtin-only", "built-in only", "built-in"),
    ]


def test_resource_listing_is_deterministic_bounded_and_reports_truncation(
    workspace_tmp_root: Path,
) -> None:
    skill_dir = _write_skill(workspace_tmp_root, "resourceful")
    for relative in ("scripts/z.py", "references/b.md", "assets/a.txt"):
        target = skill_dir / relative
        target.parent.mkdir(exist_ok=True)
        target.write_text(relative, encoding="utf-8")

    registry = SkillRegistry.discover(user_root=workspace_tmp_root, file_cap=2)
    listing = registry.list_resources("resourceful")

    assert listing.files == ("assets/a.txt", "references/b.md")
    assert listing.truncated is True
    assert "SKILL.md" not in listing.files


def test_explicit_activation_loads_once_per_turn_and_report_is_truthful(
    workspace_tmp_root: Path,
) -> None:
    _write_skill(
        workspace_tmp_root,
        "release-notes",
        description="Create release notes.",
        body="# Instructions\n\nONLY LOAD EXPLICITLY",
        compatibility="Requires a Git checkout.",
    )
    registry = SkillRegistry.discover(user_root=workspace_tmp_root)
    session = registry.create_session(eager=True, provider="offline-test")

    before = session.report()
    assert before.visible_skill_count == 1
    assert before.eager_hints_used is False
    assert before.eager_hint_payloads == ()
    assert before.loaded_instruction_bodies == ()
    assert before.provider == "offline-test"
    assert before.source_scopes == ("user",)

    activation = session.activate_explicit("/release-notes summarize v1")
    assert activation is not None
    assert activation.remaining_prompt == "summarize v1"
    assert activation.loaded is True
    assert activation.instructions == "# Instructions\n\nONLY LOAD EXPLICITLY"
    assert activation.scope == "user"

    duplicate = session.activate("release-notes")
    assert duplicate.loaded is False
    assert duplicate.instructions is None
    assert session.report().loaded_instruction_bodies == (
        {
            "name": "release-notes",
            "scope": "user",
            "source": str(
                workspace_tmp_root / ".skills" / "release-notes" / "SKILL.md"
            ),
            "chars": len("# Instructions\n\nONLY LOAD EXPLICITLY"),
            "instructions": "# Instructions\n\nONLY LOAD EXPLICITLY",
        },
    )

    session.begin_turn()
    assert session.report().loaded_instruction_bodies == ()
    assert session.activate("release-notes").loaded is True


def test_skill_layer_operates_without_api_keys(
    workspace_tmp_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for key in tuple(os.environ):
        if key.endswith("_API_KEY"):
            monkeypatch.delenv(key, raising=False)
    _write_skill(workspace_tmp_root, "offline-skill")

    session = SkillRegistry.discover(user_root=workspace_tmp_root).create_session(
        eager=True, provider="offline"
    )

    assert session.activate("offline-skill").loaded is True
    assert session.report().provider == "offline"
    assert session.report().eager_hints_used is False


def test_prepare_turn_adds_only_explicit_skill_instructions_to_agent_context(
    workspace_tmp_root: Path,
) -> None:
    _write_skill(
        workspace_tmp_root,
        "release-notes",
        body="# Instructions\n\nUse the safe release format.",
    )
    session = SkillRegistry.discover(user_root=workspace_tmp_root).create_session()
    existing = [{"role": "user", "content": "/release-notes summarize v1"}]

    ordinary = session.prepare_turn("hello", existing)
    assert ordinary.query == "hello"
    assert ordinary.context == existing
    assert ordinary.report.loaded_instruction_bodies == ()

    explicit = session.prepare_turn("/release-notes summarize v1", existing)
    assert explicit.query == "summarize v1"
    assert explicit.context == [
        *existing,
        {
            "role": "system",
            "content": "# Instructions\n\nUse the safe release format.",
        },
    ]
    assert explicit.report.loaded_instruction_bodies[0]["name"] == "release-notes"
    assert explicit.report.loaded_instruction_bodies[0]["instructions"] == (
        "# Instructions\n\nUse the safe release format."
    )


def test_eager_hints_are_injected_and_reported_only_when_used(
    workspace_tmp_root: Path,
) -> None:
    _write_skill(
        workspace_tmp_root,
        "release-notes",
        body="# When to Use\n\nUse for signed releases.\n\n# Instructions\n\nPRIVATE BODY",
    )
    registry = SkillRegistry.discover(user_root=workspace_tmp_root)

    ordinary = registry.create_session(eager=False).prepare_turn("hello", [])
    assert ordinary.context == []
    assert ordinary.report.eager_hints_used is False
    assert ordinary.report.eager_hint_payloads == ()

    eager = registry.create_session(eager=True).prepare_turn("hello", [])
    assert eager.context == [
        {
            "role": "system",
            "content": "Skill activation hint for /release-notes:\nUse for signed releases.",
        }
    ]
    assert eager.report.eager_hints_used is True
    assert eager.report.eager_hint_payloads == (
        {
            "name": "release-notes",
            "scope": "user",
            "source": str(
                workspace_tmp_root / ".skills" / "release-notes" / "SKILL.md"
            ),
            "content": "Skill activation hint for /release-notes:\nUse for signed releases.",
        },
    )
    assert "PRIVATE BODY" not in repr(eager.context)


def test_agent_delivers_activated_body_once_and_keeps_approval_gate(
    workspace_tmp_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    logger = SimpleNamespace(
        info=lambda *args, **kwargs: None,
        warning=lambda *args, **kwargs: None,
        error=lambda *args, **kwargs: None,
    )
    monkeypatch.setitem(sys.modules, "loguru", SimpleNamespace(logger=logger))

    class DummyCostTracker:
        def summary(self):
            return {"total_calls": 0, "total_cost": 0.0}

    class DummyTrace:
        def add_reasoning(self, *args, **kwargs):
            return None

        def add_decision(self, *args, **kwargs):
            return None

        def summary(self):
            return {"spans": []}

    monkeypatch.setitem(
        sys.modules, "aria.costs", SimpleNamespace(CostTracker=DummyCostTracker)
    )
    monkeypatch.setitem(sys.modules, "aria.tracing", SimpleNamespace(TraceLog=DummyTrace))
    monkeypatch.setitem(sys.modules, "aria.tools", SimpleNamespace(ToolRegistry=object))
    from aria.agents import AriaAgent
    from aria.approvals import ApprovalGate
    from aria.memory import AgentMemory
    from aria.routing import RouteDecision
    from aria.store import InMemoryApprovalStore

    instructions = "# Instructions\n\nRequire a human approval for writes."
    _write_skill(workspace_tmp_root, "safe-writes", body=instructions)
    session = SkillRegistry.discover(user_root=workspace_tmp_root).create_session()

    class RecordingRouter:
        def __init__(self) -> None:
            self.contexts = []

        def route(self, query, context, cost_tracker=None):
            self.contexts.append(context)
            return RouteDecision(
                tool="task_creator",
                arguments={"title": query, "description": query},
                strategy="recording",
            )

    router = RecordingRouter()
    store = InMemoryApprovalStore()

    class GatedRegistry:
        @staticmethod
        def names():
            return ["task_creator"]

        @staticmethod
        def requires_approval(name):
            assert name == "task_creator"
            return True

    agent = AriaAgent(
        GatedRegistry(),
        ApprovalGate(enabled=True, mode="approval_gated", store=store),
        router=router,
        memory=AgentMemory(),
        mode="approval_gated",
        skill_session=session,
    )

    result = agent.run_structured(
        "/safe-writes prepare release",
        trace=DummyTrace(),
        cost_tracker=DummyCostTracker(),
    )

    assert result.status == "pending_approval"
    assert result.approval is not None
    delivered = [
        message["content"]
        for message in router.contexts[0]
        if message["role"] == "system" and message["content"] == instructions
    ]
    assert delivered == [instructions]
    assert result.skill_context["loaded_instruction_bodies"][0]["instructions"] == (
        instructions
    )


def test_llm_router_places_skill_context_in_request_exactly_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = SimpleNamespace(warning=lambda *args, **kwargs: None)
    monkeypatch.setitem(sys.modules, "loguru", SimpleNamespace(logger=logger))
    from aria.routing import KeywordRouter, LLMRouter

    class RecordingClient:
        def __init__(self) -> None:
            self.prompts = []

        def generate(self, model, prompt, mocked_response=None):
            self.prompts.append(prompt)
            return {"response": '{"tool": null, "arguments": {}}'}

    instructions = "EXACTLY ONCE SKILL INSTRUCTION"
    client = RecordingClient()
    router = LLMRouter(
        llm_client=client,
        keyword_fallback=KeywordRouter(tool_names=["task_creator"]),
        simulate=False,
    )

    router.route(
        "prepare release",
        [{"role": "system", "content": instructions}],
    )

    assert len(client.prompts) == 1
    assert client.prompts[0].count(instructions) == 1


def test_agent_no_tool_flow_delivers_skill_to_one_provider_request(
    workspace_tmp_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    logger = SimpleNamespace(
        info=lambda *args, **kwargs: None,
        warning=lambda *args, **kwargs: None,
        error=lambda *args, **kwargs: None,
    )
    monkeypatch.setitem(sys.modules, "loguru", SimpleNamespace(logger=logger))

    class DummyCostTracker:
        def record_call(self, *args, **kwargs):
            return 0.0

        def summary(self):
            return {"total_calls": 2, "total_cost": 0.0}

    class DummyTrace:
        def add_reasoning(self, *args, **kwargs):
            return None

        def add_decision(self, *args, **kwargs):
            return None

        def summary(self):
            return {"spans": []}

    monkeypatch.setitem(
        sys.modules, "aria.costs", SimpleNamespace(CostTracker=DummyCostTracker)
    )
    monkeypatch.setitem(sys.modules, "aria.tracing", SimpleNamespace(TraceLog=DummyTrace))
    monkeypatch.setitem(sys.modules, "aria.tools", SimpleNamespace(ToolRegistry=object))
    from aria.agents import AriaAgent
    from aria.approvals import ApprovalGate
    from aria.memory import AgentMemory
    from aria.routing import KeywordRouter, LLMRouter

    instructions = "ONE_PROVIDER_CONSUMER_ONLY"
    _write_skill(workspace_tmp_root, "one-consumer", body=instructions)
    session = SkillRegistry.discover(user_root=workspace_tmp_root).create_session()

    class RecordingClient:
        def __init__(self) -> None:
            self.prompts = []

        def generate(self, model, prompt, mocked_response=None):
            self.prompts.append(prompt)
            if prompt.startswith("You are a tool router"):
                return {"response": '{"tool": null, "arguments": {}}'}
            return {"response": "direct response", "telemetry": {}}

    class EmptyRegistry:
        @staticmethod
        def names():
            return []

    client = RecordingClient()
    router = LLMRouter(
        llm_client=client,
        keyword_fallback=KeywordRouter(tool_names=[]),
        simulate=False,
    )
    agent = AriaAgent(
        EmptyRegistry(),
        ApprovalGate(enabled=True, mode="free_running"),
        router=router,
        memory=AgentMemory(),
        skill_session=session,
    )

    result = agent.run_structured(
        "/one-consumer explain the release",
        trace=DummyTrace(),
        cost_tracker=DummyCostTracker(),
    )

    assert result.status == "completed"
    assert len(client.prompts) == 2
    assert sum(prompt.count(instructions) for prompt in client.prompts) == 1
    assert instructions in client.prompts[0]
    assert instructions not in client.prompts[1]


def test_route_exception_delivers_skill_once_to_fallback_response(
    workspace_tmp_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    logger = SimpleNamespace(
        info=lambda *args, **kwargs: None,
        warning=lambda *args, **kwargs: None,
        error=lambda *args, **kwargs: None,
    )
    monkeypatch.setitem(sys.modules, "loguru", SimpleNamespace(logger=logger))

    class DummyCostTracker:
        def record_call(self, *args, **kwargs):
            return 0.0

        def summary(self):
            return {"total_calls": 1, "total_cost": 0.0}

    class DummyTrace:
        def add_reasoning(self, *args, **kwargs):
            return None

        def add_decision(self, *args, **kwargs):
            return None

        def summary(self):
            return {"spans": []}

    monkeypatch.setitem(
        sys.modules, "aria.costs", SimpleNamespace(CostTracker=DummyCostTracker)
    )
    monkeypatch.setitem(sys.modules, "aria.tracing", SimpleNamespace(TraceLog=DummyTrace))
    monkeypatch.setitem(sys.modules, "aria.tools", SimpleNamespace(ToolRegistry=object))
    from aria.agents import AriaAgent
    from aria.approvals import ApprovalGate
    from aria.memory import AgentMemory
    from aria.routing import KeywordRouter, LLMRouter

    instructions = "ROUTE_FAILURE_FALLBACK_INSTRUCTION"
    _write_skill(workspace_tmp_root, "route-fallback", body=instructions)
    session = SkillRegistry.discover(user_root=workspace_tmp_root).create_session()

    class RaisingThenRespondingClient:
        def __init__(self) -> None:
            self.prompts = []
            self.attempts = 0

        def generate(self, model, prompt, mocked_response=None):
            self.attempts += 1
            if self.attempts == 1:
                raise RuntimeError("routing provider unavailable")
            self.prompts.append(prompt)
            return {"response": "fallback response", "telemetry": {}}

    class EmptyRegistry:
        @staticmethod
        def names():
            return []

    client = RaisingThenRespondingClient()
    agent = AriaAgent(
        EmptyRegistry(),
        ApprovalGate(enabled=True, mode="free_running"),
        router=LLMRouter(
            llm_client=client,
            keyword_fallback=KeywordRouter(tool_names=[]),
            simulate=False,
        ),
        memory=AgentMemory(),
        skill_session=session,
    )

    result = agent.run_structured(
        "/route-fallback explain the release",
        trace=DummyTrace(),
        cost_tracker=DummyCostTracker(),
    )

    assert result.status == "completed"
    assert client.attempts == 2
    assert len(client.prompts) == 1
    assert sum(prompt.count(instructions) for prompt in client.prompts) == 1
    assert instructions in client.prompts[0]
