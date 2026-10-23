"""Application-only automatic skills and immutable saved-evidence projections.

Public library sessions stay explicit. Only ARIA's shipped skills are trusted;
discovery reads frontmatter, never instruction bodies.
"""

from __future__ import annotations

import hashlib
import re
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .routing import KeywordRouter
from .skills import (
    PreparedSkillTurn,
    ResourceListing,
    SkillActivation,
    SkillContextReport,
    SkillMetadata,
    SkillRegistry,
    SkillSession,
    SkillValidationError,
    _read_frontmatter_only,
    parse_skill_markdown,
)

TOOL_SKILLS = {
    "calculator": "calculator",
    "task_creator": "task-creator",
    "email_draft": "email-draft",
    "file_reader": "file-reader",
    "web_search": "web-search",
}
_SPLIT_RE = re.compile(r"\s+then\s+|\s*;\s*", re.IGNORECASE)
_MAX_SKILL_CHARS = 32768


def _source_root() -> Path:
    installed = Path(__file__).resolve().parent / "_skills"
    if installed.is_dir():
        return installed
    # Editable installations resolve only this package's own canonical source.
    return Path(__file__).resolve().parents[2] / ".agents" / "skills"


def _safe_source(root: Path, source: Path) -> Path:
    resolved = source.resolve()
    if not resolved.is_relative_to(root.resolve()) or source.is_symlink():
        raise SkillValidationError("Skill source escapes its configured source root")
    return resolved


class ApplicationSkillRegistry(SkillRegistry):
    """Known shipped capabilities with logical public source identifiers."""

    def __init__(self, root: Path):
        self.source_root = root.resolve()
        self.invalid: dict[str, str] = {}
        metadata = []
        for name in TOOL_SKILLS.values():
            source = root / name / "SKILL.md"
            try:
                document = parse_skill_markdown(
                    _read_frontmatter_only(_safe_source(root, source))
                )
                if document.name != name:
                    raise SkillValidationError(
                        "Skill identity differs from its shipped name"
                    )
                metadata.append(
                    SkillMetadata(
                        name=name,
                        description=document.description,
                        scope="builtin",
                        source=source,
                        directory=source.parent,
                        compatibility=document.compatibility,
                    )
                )
            except (OSError, UnicodeError, RuntimeError, SkillValidationError):
                self.invalid[name] = f"Shipped skill '{name}' is unavailable or invalid"
        super().__init__(tuple(metadata))

    def catalog(self, *, eager: bool = False) -> tuple[dict[str, str], ...]:
        return tuple(
            {
                "name": skill.name,
                "description": skill.description,
                "scope": "builtin",
                "source": f"builtin:{skill.name}/SKILL.md",
            }
            for skill in self
        )


@dataclass(frozen=True)
class ApplicationSkillReport(SkillContextReport):
    context_consumed: bool = False

    def to_dict(self) -> dict[str, object]:
        return {**super().to_dict(), "context_consumed": self.context_consumed}


class ApplicationSkillSession(SkillSession):
    """Fresh per-run selection state using the actual keyword tool rules."""

    def __init__(
        self, registry: ApplicationSkillRegistry, *, planning_mode: str, max_steps: int
    ):
        super().__init__(registry, eager=False, provider="keyword")
        self.planning_mode = planning_mode
        self.max_steps = max(1, max_steps)
        self.context_consumed = False
        self._selection_method = "explicit"
        self._selection_reason = "Explicit skill command"

    def begin_turn(self) -> None:
        super().begin_turn()
        self.context_consumed = False

    def activate(self, name: str) -> SkillActivation:
        registry = self.registry
        if not isinstance(registry, ApplicationSkillRegistry):
            raise SkillValidationError("Application skill registry is required")
        if name in registry.invalid:
            raise SkillValidationError(registry.invalid[name])
        skill = registry._require(name)
        source = f"builtin:{name}/SKILL.md"
        # The five shipped capabilities consist only of their canonical body.
        # Avoid traversing arbitrary newly added resource directories here.
        resources = ResourceListing(files=(), truncated=False)
        if name in self._activated_this_turn:
            return SkillActivation(name, "builtin", source, False, None, resources)
        try:
            path = _safe_source(registry.source_root, skill.source)
            with path.open("r", encoding="utf-8") as handle:
                raw = handle.read(_MAX_SKILL_CHARS + 1)
            if len(raw) > _MAX_SKILL_CHARS:
                raise SkillValidationError("Skill instructions exceed the size limit")
            document = parse_skill_markdown(raw)
            if document.name != name or not document.instructions:
                raise SkillValidationError("Skill instructions or identity are invalid")
        except (OSError, UnicodeError, RuntimeError, SkillValidationError) as exc:
            raise SkillValidationError(
                f"Shipped skill '{name}' could not be loaded safely"
            ) from exc
        self._activated_this_turn.add(name)
        self._loaded_this_turn.append(
            {
                "name": name,
                "scope": "builtin",
                "source": source,
                "chars": len(document.instructions),
                "instructions": document.instructions,
                "content_hash": hashlib.sha256(
                    document.instructions.encode()
                ).hexdigest(),
                "selection_method": self._selection_method,
                "selection_reason": self._selection_reason,
                **(
                    {"activation_command": f"/{name}"}
                    if self._selection_method == "explicit"
                    else {}
                ),
            }
        )
        return SkillActivation(
            name, "builtin", source, True, document.instructions, resources
        )

    def prepare_turn(
        self, query: str, context: list[dict[str, str]]
    ) -> PreparedSkillTurn:
        self.begin_turn()
        prepared_context = list(context)
        match = re.match(r"^/(\S+)[ \t]*([\s\S]*)$", query)
        if match is not None and match.group(1) in TOOL_SKILLS.values():
            self._selection_method = "explicit"
            self._selection_reason = f"Requested /{match.group(1)} explicitly"
            activation = self.activate(match.group(1))
            if activation.instructions:
                prepared_context.append(
                    {"role": "system", "content": activation.instructions}
                )
            query = match.group(2).strip() or query
        else:
            parts = [query]
            if self.planning_mode == "multi":
                parts = [
                    part.strip() for part in _SPLIT_RE.split(query) if part.strip()
                ][: self.max_steps]
            for part in parts:
                decision = KeywordRouter().route(part)
                if decision.tool not in TOOL_SKILLS:
                    continue
                self._selection_method = "automatic"
                self._selection_reason = (
                    f"{decision.rationale}; selected {decision.tool} capability"
                )
                activation = self.activate(TOOL_SKILLS[decision.tool])
                if activation.instructions:
                    prepared_context.append(
                        {"role": "system", "content": activation.instructions}
                    )
        return PreparedSkillTurn(
            query=query, context=prepared_context, report=self.report()
        )

    def report(self) -> ApplicationSkillReport:
        report = super().report()
        return ApplicationSkillReport(
            visible_skill_count=report.visible_skill_count,
            eager_hints_used=report.eager_hints_used,
            eager_hint_payloads=report.eager_hint_payloads,
            loaded_instruction_bodies=report.loaded_instruction_bodies,
            provider=report.provider,
            source_scopes=report.source_scopes,
            context_consumed=self.context_consumed,
        )


def create_api_skill_session(
    *, planning_mode: str = "single", max_steps: int = 5
) -> ApplicationSkillSession:
    if planning_mode not in {"single", "multi"}:
        raise ValueError("planning_mode must be single or multi")
    return ApplicationSkillSession(
        ApplicationSkillRegistry(_source_root()),
        planning_mode=planning_mode,
        max_steps=max_steps,
    )


def build_skills_snapshot(
    *, session_id: str, run: dict[str, Any] | None
) -> dict[str, Any]:
    """Project saved evidence; viewing it never loads or activates a body."""
    catalog = list(ApplicationSkillRegistry(_source_root()).catalog())
    run_id = run.get("run_id", run.get("id")) if run else None
    saved = run.get("skill_context") if run else None
    available = isinstance(saved, dict)
    report = (
        deepcopy(saved)
        if available
        else {
            "visible_skill_count": len(catalog),
            "eager_hints_used": False,
            "eager_hint_payloads": [],
            "loaded_instruction_bodies": [],
            "provider": "unknown",
            "source_scopes": ["builtin"],
            "context_consumed": False,
        }
    )
    activated = []
    for body in report.get("loaded_instruction_bodies", []):
        entry = deepcopy(body)
        entry["scope"] = {"built-in": "builtin"}.get(
            entry.get("scope"), entry.get("scope")
        )
        # Legacy reports may contain machine paths. Keep their content evidence
        # but expose only a portable identifier.
        entry["source"] = f"{entry.get('scope', 'builtin')}:{entry['name']}/SKILL.md"
        entry.update(run_id=run_id, loaded=True)
        activated.append(entry)
    report["loaded_instruction_bodies"] = [
        {key: value for key, value in entry.items() if key not in {"run_id", "loaded"}}
        for entry in activated
    ]
    report["source_scopes"] = [
        "builtin" if scope == "built-in" else scope
        for scope in report.get("source_scopes", [])
    ]
    return {
        "catalog": catalog,
        "activated": activated,
        "context_report": report,
        "session_id": session_id,
        "run_id": run_id,
        "context_available": available,
    }
