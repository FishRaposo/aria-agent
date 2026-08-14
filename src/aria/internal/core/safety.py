"""Dependency-free prompt-injection/content-risk checks."""

from __future__ import annotations

import re
from typing import Iterable

from .contracts import SafetyAssessment


class SafetyClassifier:
    """Conservative deterministic classifier for obvious instruction attacks."""

    _PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
        (
            "ignore previous instructions",
            re.compile(r"ignore\s+(?:all\s+)?previous\s+instructions", re.I),
        ),
        (
            "reveal system prompt",
            re.compile(r"(?:reveal|show|print)\s+(?:the\s+)?system\s+prompt", re.I),
        ),
        (
            "bypass safety",
            re.compile(r"bypass\s+(?:your\s+)?safety", re.I),
        ),
        (
            "developer instruction override",
            re.compile(r"you\s+are\s+now\s+the\s+developer", re.I),
        ),
    )

    def __init__(self, *, policy: str = "warn") -> None:
        if policy not in {"off", "warn", "block"}:
            raise ValueError("policy must be off, warn, or block")
        self.policy = policy

    def assess(
        self,
        query: str,
        context: Iterable[str] | None = None,
        arguments: object | None = None,
    ) -> SafetyAssessment:
        if self.policy == "off":
            return SafetyAssessment(reason="safety policy disabled")
        haystack = "\n".join(
            [query, *(context or ()), repr(arguments) if arguments is not None else ""]
        )
        matches = tuple(
            label for label, pattern in self._PATTERNS if pattern.search(haystack)
        )
        if not matches:
            return SafetyAssessment()
        action = "block" if self.policy == "block" else "warn"
        return SafetyAssessment(
            risk="high",
            action=action,
            matches=matches,
            reason="known instruction-override pattern detected",
        )
