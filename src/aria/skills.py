"""Bounded, offline progressive disclosure for ``SKILL.md`` capabilities.

Discovery exposes metadata only. Instruction bodies are read again and returned
only when a caller explicitly activates a skill through :class:`SkillSession`.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Mapping, Optional, Tuple

import yaml

LOGGER = logging.getLogger(__name__)

_SKILL_DIRECTORIES = (Path(".skills"), Path(".agents") / "skills")
_FRONTMATTER = re.compile(
    r"^---\r?\n(?P<frontmatter>[\s\S]*?)\r?\n---(?:\r?\n)?(?P<body>[\s\S]*)$"
)
_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_HINT_HEADING = re.compile(r"\b(?:when to use|triggers?)\b", re.IGNORECASE)
_EXPLICIT_ACTIVATION = re.compile(r"^/(\S+)[ \t]*([\s\S]*)$")


class SkillValidationError(ValueError):
    """Raised when a ``SKILL.md`` file lacks its required structure."""


@dataclass(frozen=True)
class SkillDocument:
    """A parsed skill document returned by the standalone parser."""

    name: str
    description: str
    instructions: str
    compatibility: Optional[str] = None


@dataclass(frozen=True)
class SkillMetadata:
    """Level-one discovery record; it deliberately contains no body."""

    name: str
    description: str
    scope: str
    source: Path
    directory: Path
    compatibility: Optional[str] = None


@dataclass(frozen=True)
class ResourceListing:
    """A bounded listing of resources shipped beside one ``SKILL.md``."""

    files: Tuple[str, ...]
    truncated: bool


@dataclass(frozen=True)
class SkillActivation:
    """Result of an explicit activation attempt in the current turn."""

    name: str
    scope: str
    source: str
    loaded: bool
    instructions: Optional[str]
    resources: ResourceListing
    remaining_prompt: Optional[str] = None


@dataclass(frozen=True)
class SkillContextReport:
    """Structured evidence of what skill content entered this turn's context."""

    visible_skill_count: int
    eager_hints_used: bool
    eager_hint_payloads: Tuple[Dict[str, object], ...]
    loaded_instruction_bodies: Tuple[Dict[str, object], ...]
    provider: str
    source_scopes: Tuple[str, ...]

    def to_dict(self) -> Dict[str, object]:
        """Return an API-safe representation for traces and run results."""
        return {
            "visible_skill_count": self.visible_skill_count,
            "eager_hints_used": self.eager_hints_used,
            "eager_hint_payloads": [dict(item) for item in self.eager_hint_payloads],
            "loaded_instruction_bodies": [
                dict(item) for item in self.loaded_instruction_bodies
            ],
            "provider": self.provider,
            "source_scopes": list(self.source_scopes),
        }


@dataclass(frozen=True)
class PreparedSkillTurn:
    """Query and context prepared for ARIA without changing its tool loop."""

    query: str
    context: List[Dict[str, str]]
    report: SkillContextReport


def parse_skill_markdown(raw: str) -> SkillDocument:
    """Parse YAML frontmatter and validate the required skill fields."""
    match = _FRONTMATTER.match(raw.lstrip("\ufeff"))
    if match is None:
        raise SkillValidationError(
            "SKILL.md must start with YAML frontmatter delimited by ---"
        )
    try:
        frontmatter = yaml.safe_load(match.group("frontmatter"))
    except yaml.YAMLError as exc:
        raise SkillValidationError(f"invalid YAML frontmatter: {exc}") from exc
    if not isinstance(frontmatter, Mapping):
        raise SkillValidationError("frontmatter must be a YAML mapping")

    name = frontmatter.get("name")
    if not isinstance(name, str) or not name.strip():
        raise SkillValidationError('"name" is required and must be a non-empty string')
    description = frontmatter.get("description")
    if not isinstance(description, str) or not description.strip():
        raise SkillValidationError(
            '"description" is required and must be a non-empty string'
        )
    compatibility = frontmatter.get("compatibility")
    if compatibility is not None and not isinstance(compatibility, str):
        compatibility = None
    return SkillDocument(
        name=name.strip(),
        description=description.strip(),
        instructions=match.group("body").strip(),
        compatibility=compatibility.strip() if compatibility else None,
    )


class SkillRegistry:
    """Deterministic metadata registry spanning project, user and built-in scopes."""

    def __init__(
        self, skills: Tuple[SkillMetadata, ...], *, file_cap: int = 50
    ) -> None:
        if file_cap < 0:
            raise ValueError("file_cap must be non-negative")
        self._skills = skills
        self._by_name = {skill.name: skill for skill in skills}
        self.file_cap = file_cap

    @classmethod
    def discover(
        cls,
        *,
        project_root: Optional[Path] = None,
        user_root: Optional[Path] = None,
        builtin_root: Optional[Path] = None,
        trust_project: bool = False,
        file_cap: int = 50,
    ) -> "SkillRegistry":
        """Discover metadata with project > user > built-in precedence.

        Project files are considered only when ``trust_project`` is true. Within
        each scope ``.skills`` precedes ``.agents/skills`` and directory names
        are sorted for repeatable results.
        """
        scopes = []
        if trust_project and project_root is not None:
            scopes.append(("project", Path(project_root)))
        if user_root is not None:
            scopes.append(("user", Path(user_root)))
        if builtin_root is not None:
            scopes.append(("built-in", Path(builtin_root)))

        discovered = []
        claimed = set()
        for scope, root in scopes:
            for metadata in _discover_scope(root, scope):
                if metadata.name in claimed:
                    LOGGER.info(
                        "Skipping shadowed skill %s from %s scope",
                        metadata.name,
                        scope,
                    )
                    continue
                claimed.add(metadata.name)
                discovered.append(metadata)
        return cls(tuple(discovered), file_cap=file_cap)

    def __iter__(self) -> Iterator[SkillMetadata]:
        return iter(self._skills)

    def __len__(self) -> int:
        return len(self._skills)

    def catalog(self, *, eager: bool = False) -> Tuple[Dict[str, str], ...]:
        """Return level-one metadata, optionally enriched with level-1.5 hints."""
        entries = []
        for skill in self._skills:
            entry = {
                "name": skill.name,
                "description": skill.description,
                "scope": skill.scope,
                "source": str(skill.source),
            }
            if eager:
                activation_hints = _load_activation_hints(skill)
                if activation_hints:
                    entry["activation_hints"] = activation_hints
            entries.append(entry)
        return tuple(entries)

    def list_resources(
        self, name: str, *, file_cap: Optional[int] = None
    ) -> ResourceListing:
        """List resource paths without reading their contents."""
        skill = self._require(name)
        cap = self.file_cap if file_cap is None else file_cap
        if cap < 0:
            raise ValueError("file_cap must be non-negative")
        return _list_resources(skill.directory, cap)

    def create_session(
        self, *, eager: bool = False, provider: str = "offline"
    ) -> "SkillSession":
        """Create an offline activation session over this registry."""
        return SkillSession(self, eager=eager, provider=provider)

    def _require(self, name: str) -> SkillMetadata:
        try:
            return self._by_name[name]
        except KeyError as exc:
            raise KeyError(f'no skill named "{name}"') from exc


class SkillSession:
    """Per-consumer state for explicit, same-turn-deduplicated activation."""

    def __init__(self, registry: SkillRegistry, *, eager: bool, provider: str) -> None:
        self.registry = registry
        self.eager = eager
        self.provider = provider
        self._activated_this_turn = set()
        self._loaded_this_turn = []
        self._eager_hint_payloads = []

    def begin_turn(self) -> None:
        """Reset per-turn activation evidence and duplicate suppression."""
        self._activated_this_turn.clear()
        self._loaded_this_turn.clear()
        self._eager_hint_payloads.clear()

    def activate(self, name: str) -> SkillActivation:
        """Explicitly load a skill body once in this turn."""
        skill = self.registry._require(name)
        resources = self.registry.list_resources(name)
        if name in self._activated_this_turn:
            return SkillActivation(
                name=name,
                scope=skill.scope,
                source=str(skill.source),
                loaded=False,
                instructions=None,
                resources=resources,
            )

        document = parse_skill_markdown(skill.source.read_text(encoding="utf-8"))
        self._activated_this_turn.add(name)
        self._loaded_this_turn.append(
            {
                "name": name,
                "scope": skill.scope,
                "source": str(skill.source),
                "chars": len(document.instructions),
                "instructions": document.instructions,
            }
        )
        return SkillActivation(
            name=name,
            scope=skill.scope,
            source=str(skill.source),
            loaded=True,
            instructions=document.instructions,
            resources=resources,
        )

    def activate_explicit(self, prompt: str) -> Optional[SkillActivation]:
        """Activate a leading ``/skill-name`` token; unmatched tokens fall through."""
        match = _EXPLICIT_ACTIVATION.match(prompt)
        if match is None or match.group(1) not in self.registry._by_name:
            return None
        activation = self.activate(match.group(1))
        return SkillActivation(
            name=activation.name,
            scope=activation.scope,
            source=activation.source,
            loaded=activation.loaded,
            instructions=activation.instructions,
            resources=activation.resources,
            remaining_prompt=match.group(2).strip(),
        )

    def prepare_turn(
        self, query: str, context: List[Dict[str, str]]
    ) -> PreparedSkillTurn:
        """Prepare optional explicit skill context for one ARIA run."""
        self.begin_turn()
        prepared_context = list(context)
        if self.eager:
            for entry in self.registry.catalog(eager=True):
                hint = entry.get("activation_hints")
                if not hint:
                    continue
                payload = f"Skill activation hint for /{entry['name']}:\n{hint}"
                prepared_context.append({"role": "system", "content": payload})
                self._eager_hint_payloads.append(
                    {
                        "name": entry["name"],
                        "scope": entry["scope"],
                        "source": entry["source"],
                        "content": payload,
                    }
                )
        activation = self.activate_explicit(query)
        if activation is None or activation.instructions is None:
            return PreparedSkillTurn(
                query=query, context=prepared_context, report=self.report()
            )
        return PreparedSkillTurn(
            query=activation.remaining_prompt or query,
            context=[
                *prepared_context,
                {"role": "system", "content": activation.instructions},
            ],
            report=self.report(),
        )

    def report(self) -> SkillContextReport:
        """Report only instruction bodies actually loaded in the current turn."""
        scopes = tuple(dict.fromkeys(skill.scope for skill in self.registry))
        return SkillContextReport(
            visible_skill_count=len(self.registry),
            eager_hints_used=bool(self._eager_hint_payloads),
            eager_hint_payloads=tuple(
                dict(item) for item in self._eager_hint_payloads
            ),
            loaded_instruction_bodies=tuple(
                dict(item) for item in self._loaded_this_turn
            ),
            provider=self.provider,
            source_scopes=scopes,
        )


def _discover_scope(root: Path, scope: str) -> Iterator[SkillMetadata]:
    claimed = set()
    for relative in _SKILL_DIRECTORIES:
        skill_root = root / relative
        if not skill_root.is_dir():
            continue
        try:
            directories = sorted(
                (path for path in skill_root.iterdir() if path.is_dir()),
                key=lambda path: path.name,
            )
        except OSError as exc:
            LOGGER.warning("Skipping skill directory %s: %s", skill_root, exc)
            continue
        for directory in directories:
            source = directory / "SKILL.md"
            if not source.is_file():
                continue
            try:
                document = _parse_metadata_frontmatter(
                    _read_frontmatter_only(source)
                )
            except (OSError, UnicodeError, SkillValidationError) as exc:
                LOGGER.warning("Skipping invalid skill %s: %s", source, exc)
                continue
            if document.name in claimed:
                continue
            claimed.add(document.name)
            yield SkillMetadata(
                name=document.name,
                description=document.description,
                scope=scope,
                source=source,
                directory=directory,
                compatibility=document.compatibility,
            )


def _read_frontmatter_only(source: Path, *, max_chars: int = 8192) -> str:
    """Read through the closing frontmatter delimiter, never the body."""
    chunks = []
    chars = 0
    delimiters = 0
    with source.open("r", encoding="utf-8") as handle:
        for line in handle:
            chars += len(line)
            if chars > max_chars:
                raise SkillValidationError(
                    f"frontmatter exceeds the {max_chars}-character discovery cap"
                )
            chunks.append(line)
            if line.rstrip("\r\n") == "---":
                delimiters += 1
                if delimiters == 2:
                    break
    if delimiters != 2:
        raise SkillValidationError("SKILL.md must contain closed YAML frontmatter")
    return "".join(chunks)


def _parse_metadata_frontmatter(raw: str) -> SkillDocument:
    """Reuse strict parsing while supplying no level-two instruction body."""
    return parse_skill_markdown(f"{raw.rstrip()}\n")


def _load_activation_hints(
    skill: SkillMetadata, *, max_read_chars: int = 16384
) -> Optional[str]:
    """Read a bounded prefix only for an explicitly eager level-1.5 catalogue."""
    try:
        with skill.source.open("r", encoding="utf-8") as handle:
            prefix = handle.read(max_read_chars)
        document = parse_skill_markdown(prefix)
    except (OSError, UnicodeError, SkillValidationError) as exc:
        LOGGER.warning("Unable to read eager hints from %s: %s", skill.source, exc)
        return None
    return _extract_activation_hints(document)


def _extract_activation_hints(
    document: SkillDocument, *, max_chars: int = 600
) -> Optional[str]:
    parts = []
    if document.compatibility:
        parts.append(f"Compatibility: {document.compatibility}")
    section = _extract_hint_section(document.instructions)
    if section:
        parts.append(section)
    if not parts:
        return None
    hints = "\n".join(parts)
    if len(hints) <= max_chars:
        return hints
    return hints[:max_chars].rstrip() + " ..."


def _extract_hint_section(body: str) -> Optional[str]:
    lines = body.splitlines()
    start = None
    depth = 0
    for index, line in enumerate(lines):
        heading = _HEADING.match(line)
        if heading and _HINT_HEADING.search(heading.group(2)):
            start = index + 1
            depth = len(heading.group(1))
            break
    if start is None:
        return None
    section = []
    in_fence = False
    for line in lines[start:]:
        if line.startswith("```"):
            in_fence = not in_fence
        heading = _HEADING.match(line)
        if not in_fence and heading and len(heading.group(1)) <= depth:
            break
        section.append(line)
    hint = "\n".join(section).strip()
    return hint or None


def _list_resources(directory: Path, cap: int) -> ResourceListing:
    files = []

    def walk(current: Path, prefix: Path) -> bool:
        try:
            entries = sorted(current.iterdir(), key=lambda path: path.name)
        except OSError:
            return False
        for entry in entries:
            relative = prefix / entry.name
            if entry.is_symlink():
                continue
            if entry.is_dir():
                if walk(entry, relative):
                    return True
            elif entry.is_file() and not (
                prefix == Path() and entry.name == "SKILL.md"
            ):
                if len(files) >= cap:
                    return True
                files.append(relative.as_posix())
        return False

    truncated = walk(directory, Path())
    return ResourceListing(files=tuple(files), truncated=truncated)


__all__ = [
    "PreparedSkillTurn",
    "ResourceListing",
    "SkillActivation",
    "SkillContextReport",
    "SkillDocument",
    "SkillMetadata",
    "SkillRegistry",
    "SkillSession",
    "SkillValidationError",
    "parse_skill_markdown",
]
