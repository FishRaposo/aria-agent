"""Task classifier — maps a free-form task description to a TaskType.

v1 is rule-based (keyword matching). Fast, deterministic, no API calls. v2
can use an LLM to handle ambiguous cases; the rule-based version stays as
the fast path and fallback.

The classifier is intentionally simple: it returns the FIRST task type whose
keyword set matches. Order in the keyword tables determines priority. If
nothing matches, returns TaskType.GENERAL.
"""
import re
from typing import Optional

from .routing_table import TaskType


# Keyword rules: ordered by priority. First match wins.
# Each rule: (task_type, [keyword, ...])
# Use lowercase, exact substring match (cheap and predictable).
_KEYWORD_RULES: list[tuple[TaskType, list[str]]] = [
    # Vision first — image-y keywords are highly specific
    (TaskType.VISION, ["image", "picture", "screenshot", "photo", "diagram", "sketch"]),

    # Code review
    (TaskType.CODE_REVIEW, ["review this", "code review", "review my", "look at this code"]),

    # Long-horizon coding / agentic
    (
        TaskType.CODING_LONG_HORIZON,
        ["autonomous", "multi-step", "build a", "implement a", "agent", "end-to-end"],
    ),

    # Frontend / UI
    (
        TaskType.FRONTEND_UI,
        ["frontend", "ui", "ux", "react component", "css", "html", "tailwind", "design"],
    ),

    # Long context
    (
        TaskType.LONG_CONTEXT,
        ["large repo", "1m tokens", "entire codebase", "whole file", "long document"],
    ),

    # Bulk transforms
    (
        TaskType.BULK_TRANSFORM,
        ["format", "transform", "convert all", "rename", "bulk", "csv", "every line"],
    ),

    # Translation
    (
        TaskType.TRANSLATION,
        ["translate", "translation", "in portuguese", "in spanish", "to french"],
    ),

    # Reasoning / math
    (
        TaskType.REASONING,
        ["prove", "theorem", "math", "equation", "calculate the probability", "logic"],
    ),

    # Writing (general prose, not code)
    (
        TaskType.WRITING,
        ["essay", "blog post", "marketing copy", "draft an email", "write a story"],
    ),

    # Cron / background
    (TaskType.CRON_BUDGET, ["cron", "background", "scheduled", "batch job"]),

    # Escalation signal — user says "best", "smartest", "frontier"
    (
        TaskType.ESCALATION,
        ["best model", "frontier", "smartest", "highest quality", "no compromise"],
    ),

    # Default coding (broad match — last because it overlaps with many above)
    (
        TaskType.CODING_DEFAULT,
        ["code", "function", "class", "bug", "fix", "implement", "script", "python", "javascript"],
    ),
]


# Heuristic: detect "give me the best" pattern (exclamation + comparison words)
_ESCALATION_RE = re.compile(
    r"\b(best|smartest|frontier|highest|most capable|top.?tier)\b", re.IGNORECASE
)


class TaskClassifier:
    """Classify a free-form task into a TaskType.

    v1 is rule-based. The classifier can be extended with an LLM-based
    fallback in v2 — the interface (`classify`) is the same.
    """

    def classify(self, task: str) -> TaskType:
        """Return the best TaskType for a given task description.

        Falls back to GENERAL if no keyword matches.
        """
        if not task or not task.strip():
            return TaskType.GENERAL

        lowered = task.lower()

        # Priority 1: explicit escalation signal
        if _ESCALATION_RE.search(task):
            return TaskType.ESCALATION

        # Priority 2: keyword rules in order
        for task_type, keywords in _KEYWORD_RULES:
            for kw in keywords:
                if kw in lowered:
                    return task_type

        # Priority 3: heuristic — long task descriptions lean toward long_context
        if len(task) > 4000:
            return TaskType.LONG_CONTEXT

        # Default
        return TaskType.GENERAL


_default_classifier: Optional[TaskClassifier] = None


def get_default_classifier() -> TaskClassifier:
    """Return the process-wide default classifier."""
    global _default_classifier
    if _default_classifier is None:
        _default_classifier = TaskClassifier()
    return _default_classifier
