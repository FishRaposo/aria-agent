"""Stable, JSON-friendly contracts for ARIA execution."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from enum import Enum
from typing import Any, Mapping, Optional


class RunEventType(str, Enum):
    """Event names emitted by the synchronous and SSE execution paths."""

    REASONING = "reasoning"
    DECISION = "decision"
    APPROVAL = "approval"
    TOOL = "tool"
    ERROR = "error"
    COMPLETE = "complete"


@dataclass(frozen=True)
class PlanStep:
    """One validated tool action in an execution plan."""

    tool: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    label: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        data = {"tool": self.tool, "arguments": dict(self.arguments)}
        if self.label is not None:
            data["label"] = self.label
        return data


@dataclass(frozen=True)
class ExecutionPlan:
    """A bounded plan produced by a deterministic or LLM-backed planner."""

    steps: tuple[PlanStep, ...] = ()
    strategy: str = "keyword"
    rationale: str = ""

    def bounded(self, max_steps: int) -> "ExecutionPlan":
        """Return a plan truncated to a positive execution budget."""
        if max_steps < 1:
            return replace(self, steps=())
        return replace(self, steps=self.steps[:max_steps])

    def to_dict(self) -> dict[str, Any]:
        return {
            "steps": [step.to_dict() for step in self.steps],
            "strategy": self.strategy,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class RunEvent:
    """A deterministic event envelope suitable for SSE or evidence output."""

    sequence: int
    event_type: RunEventType
    payload: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "type": self.event_type.value,
            "payload": dict(self.payload),
        }


@dataclass(frozen=True)
class SafetyAssessment:
    """Result of the local, deterministic safety classifier."""

    risk: str = "low"
    action: str = "allow"
    matches: tuple[str, ...] = ()
    reason: str = "no known injection pattern"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["matches"] = list(self.matches)
        return data


@dataclass(frozen=True)
class ReplayResult:
    """Normalized result of replaying a persisted run trace."""

    run_id: str
    dry_run: bool
    steps: tuple[Mapping[str, Any], ...] = ()
    side_effects_executed: bool = False
    status: str = "completed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "dry_run": self.dry_run,
            "steps": [dict(step) for step in self.steps],
            "side_effects_executed": self.side_effects_executed,
            "status": self.status,
        }
