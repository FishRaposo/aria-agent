"""Cooperation patterns — multiple models working together on one task.

This is the heart of the new direction: instead of one model doing everything,
a cooperation pattern orchestrates several models in different roles.

Three patterns ship in v1:

- **Cascade/Escalation**: try the cheap model first; escalate to a better
  model if the cheap output is judged low-quality. Saves credits for routine
  tasks; only pays for quality when needed.

- **Plan-Execute-Validate**: three roles, three models.
    1. Planner (cheap model) — drafts an approach
    2. Executor (best-fit model for the task) — does the work
    3. Validator (different model) — checks the output, sends feedback
  The validator's verdict determines whether we return the output or retry.

- **Specialized Ensemble**: decompose the task into sub-tasks, route each to
  the best specialist, combine results. Useful when one task needs vision +
  code + reasoning in different parts.

Each pattern is a class with one async method `execute(task, router, registry)`
that returns a `CooperationResult`.
"""
from .base import (
    CooperationPattern,
    CooperationResult,
    StepResult,
    QualityAssessment,
    assess_quality,
)
from .cascade import CascadePattern
from .plan_execute import PlanExecuteValidatePattern
from .ensemble import EnsemblePattern


__all__ = [
    "CooperationPattern",
    "CooperationResult",
    "StepResult",
    "QualityAssessment",
    "assess_quality",
    "CascadePattern",
    "PlanExecuteValidatePattern",
    "EnsemblePattern",
]
