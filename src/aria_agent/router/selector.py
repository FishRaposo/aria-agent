"""Model selector — picks the best model for a task type.

Given a `TaskType` (from the classifier) and a `RoutingTable` (the catalog),
the selector returns a `RoutingDecision` containing:
- The primary model to use
- An optional fallback chain (if the primary fails)
- An optional escalation target (if the user wants best quality)

The selector applies the per-task rules from the model-router skill's
decision-playbook.md (port of those tables into code).
"""
from dataclasses import dataclass, field
from typing import Optional

from .routing_table import ModelInfo, RoutingTable, SubAgentRole, TaskType, ModelTier


@dataclass(frozen=True)
class RoutingDecision:
    """The router's output: which model to use, with fallback and escalation."""

    primary: ModelInfo
    fallback: Optional[ModelInfo] = None          # if primary fails
    escalation: Optional[ModelInfo] = None        # if user wants best quality
    task_type: TaskType = TaskType.GENERAL
    reason: str = ""                              # human-readable explanation


class ModelSelector:
    """Pick the best model for a TaskType using the routing table.

    Strategy:
    1. Find all models that support the task, sorted by tier + TB score.
    2. Primary = first non-Pro+ model (active pool preferred).
    3. Fallback = first cheap-workhorse or lower-cost alternative.
    4. Escalation = first BEST_QUALITY or top TB score.

    The selector is a pure function of (table, task_type). No I/O. The agent
    does the actual model call.
    """

    def __init__(self, table: RoutingTable):
        self._table = table

    def select(
        self,
        task_type: TaskType,
        *,
        prefer_tier: Optional[ModelTier] = None,
        budget: Optional[str] = None,  # "cheap" | "balanced" | "quality"
    ) -> RoutingDecision:
        """Pick the best model for the task.

        Args:
            task_type: What the user is trying to do
            prefer_tier: Override the default tier preference
            budget: "cheap" forces cheap-workhorse; "quality" forces best-quality;
                    "balanced" uses the default tier preference
        """
        candidates = self._table.find_by_task(task_type)
        if not candidates:
            # No model claims this task — fall back to general/default
            return self._default_decision(task_type)

        # When budget is set, expand candidates to include tier-matching models
        # that didn't formally claim the task. This lets "cheap" route through
        # mimo-v2.5 even if the task type doesn't list it.
        if budget == "cheap":
            for m in self._table.cheap_pool():
                if m not in candidates:
                    candidates.append(m)
        elif budget == "quality":
            for m in self._table.all():
                if m.tier == ModelTier.BEST_QUALITY and m not in candidates:
                    candidates.append(m)

        # Apply budget preference to narrow the candidates
        primary = self._pick_primary(candidates, prefer_tier, budget)
        fallback = self._pick_fallback(candidates, primary)
        escalation = self._pick_escalation(candidates, primary)

        reason = self._explain_choice(primary, task_type, budget)
        return RoutingDecision(
            primary=primary,
            fallback=fallback,
            escalation=escalation,
            task_type=task_type,
            reason=reason,
        )

    def select_for_task_description(self, description: str) -> RoutingDecision:
        """Convenience: classify + select in one call."""
        from .classifier import get_default_classifier

        task_type = get_default_classifier().classify(description)
        return self.select(task_type)

    def select_for_role(
        self,
        role: "SubAgentRole | str",
        *,
        budget: Optional[str] = None,  # "cheap" | "balanced" | "quality"
    ) -> RoutingDecision:
        """Pick the best model for a sub-agent role.

        Accepts either a SubAgentRole enum or its string value (e.g.,
        "planner" or SubAgentRole.PLANNER). Strings are auto-converted.

        Mirrors `select()` for task types: specialists win, fallback to
        generalist (default model), fallback to cheap workhorse.

        Budget override:
        - "cheap": force the cheap workhorse regardless of role
        - "quality": force the highest-TB-score active-pool model
        - "balanced" or None: use the role's preferred model (default behavior)

        Sub-agents use this to get the right model for their job:
        - planner → kimi-k2.6 (best for deep reasoning)
        - debugger → deepseek-v4-pro (long context, logical analysis)
        - implementer → MiniMax-M3 (default, native coding)
        - etc.
        """
        # Accept both enum and string for ergonomics
        if isinstance(role, str):
            from .routing_table import SubAgentRole as _SAR
            try:
                role = _SAR(role)
            except ValueError:
                # Unknown role string — fall back
                return self._default_decision_for_role_str(role)

        candidates = self._table.find_by_role(role)
        if not candidates:
            # No model claims this role — fall back to default
            return self._default_decision_for_role(role)

        # Budget override
        if budget == "cheap":
            for m in candidates:
                if m.tier == ModelTier.CHEAP_WORKHORSE:
                    return RoutingDecision(
                        primary=m, task_type=TaskType.GENERAL,
                        reason=f"Role '{role.value}' forced to cheap workhorse.",
                    )
            # No cheap in candidates; expand to include cheap workhorse
            for m in self._table.cheap_pool():
                return RoutingDecision(
                    primary=m, task_type=TaskType.GENERAL,
                    reason=f"Role '{role.value}' forced to cheap workhorse (expanded).",
                )
        elif budget == "quality":
            # Pick highest-TB-score candidate, including Pro+ if any
            expanded = list(candidates) + [
                m for m in self._table.all()
                if m.tier == ModelTier.PRO_PLUS and m not in candidates
            ]
            expanded.sort(key=lambda m: -(m.terminal_bench_score or 0))
            if expanded:
                return RoutingDecision(
                    primary=expanded[0], task_type=TaskType.GENERAL,
                    reason=f"Role '{role.value}' forced to quality pick.",
                )

        # Default: first candidate (already tier-sorted by find_by_role)
        primary = candidates[0]
        # Fallback: second candidate, or cheap pool
        fallback = candidates[1] if len(candidates) > 1 else None
        if fallback is None:
            cheap_pool = self._table.cheap_pool()
            for m in cheap_pool:
                if m.model_id != primary.model_id:
                    fallback = m
                    break

        # Escalation: highest-TB candidate (excluding primary) or Pro+
        escalation = None
        ranked = sorted(
            [m for m in candidates if m.model_id != primary.model_id],
            key=lambda m: -(m.terminal_bench_score or 0),
        )
        escalation = ranked[0] if ranked else None

        return RoutingDecision(
            primary=primary,
            fallback=fallback,
            escalation=escalation,
            task_type=TaskType.GENERAL,
            reason=self._explain_role_choice(primary, role, budget),
        )

    def _default_decision_for_role(self, role: SubAgentRole) -> RoutingDecision:
        """Used when no model claims the given role."""
        default = self._table.default_model()
        return RoutingDecision(
            primary=default,
            fallback=self._table.cheap_pool()[0] if self._table.cheap_pool() else None,
            task_type=TaskType.GENERAL,
            reason=f"No model claims role '{role.value}'; using default.",
        )

    def _default_decision_for_role_str(self, role: str) -> RoutingDecision:
        """Used when an unknown role string is passed."""
        default = self._table.default_model()
        return RoutingDecision(
            primary=default,
            fallback=self._table.cheap_pool()[0] if self._table.cheap_pool() else None,
            task_type=TaskType.GENERAL,
            reason=f"Unknown role '{role}'; using default.",
        )

    def _explain_role_choice(
        self,
        primary: ModelInfo,
        role: SubAgentRole,
        budget: Optional[str],
    ) -> str:
        bits = [
            f"Role '{role.value}' → {primary.model_id} "
            f"on {primary.provider_name} (tier: {primary.tier.value})"
        ]
        if primary.terminal_bench_score:
            bits.append(f"TB: {primary.terminal_bench_score:.1f}%")
        if budget:
            bits.append(f"budget: {budget}")
        if primary.notes:
            bits.append(f"— {primary.notes}")
        return " · ".join(bits)

    def _default_decision(self, task_type: TaskType) -> RoutingDecision:
        """Used when no model claims the given task type."""
        default = self._table.default_model()
        return RoutingDecision(
            primary=default,
            fallback=self._table.cheap_pool()[0] if self._table.cheap_pool() else None,
            task_type=task_type,
            reason=f"No model claims task '{task_type.value}'; using default.",
        )

    def _pick_primary(
        self,
        candidates: list[ModelInfo],
        prefer_tier: Optional[ModelTier],
        budget: Optional[str],
    ) -> ModelInfo:
        """Pick the primary model from candidates based on budget preference."""
        # Budget override takes priority
        if budget == "cheap":
            for m in candidates:
                if m.tier == ModelTier.CHEAP_WORKHORSE:
                    return m
        elif budget == "quality":
            for m in candidates:
                if m.tier in (ModelTier.BEST_QUALITY, ModelTier.DEFAULT):
                    return m

        # Tier preference
        if prefer_tier:
            for m in candidates:
                if m.tier == prefer_tier:
                    return m

        # Default: first non-Pro+ model (active pool preferred)
        for m in candidates:
            if m.tier != ModelTier.PRO_PLUS:
                return m
        # Fallback: first candidate (Pro+ if that's all we have)
        return candidates[0]

    def _pick_fallback(
        self, candidates: list[ModelInfo], primary: ModelInfo
    ) -> Optional[ModelInfo]:
        """Pick a cheaper/simpler alternative if the primary fails.

        Always returns something — at minimum, the default model. This way
        the calling code can rely on `decision.fallback` being non-None for
        any non-trivial task.
        """
        # Prefer cheap workhorse
        for m in candidates:
            if m.tier == ModelTier.CHEAP_WORKHORSE and m.model_id != primary.model_id:
                return m
        # Otherwise, any candidate with lower cost
        cheaper = [
            m for m in candidates
            if m.model_id != primary.model_id
            and m.cost_per_1m_input <= primary.cost_per_1m_input
        ]
        if cheaper:
            return cheaper[0]
        # Last resort: the cheap pool from the table
        cheap_pool = self._table.cheap_pool()
        for m in cheap_pool:
            if m.model_id != primary.model_id:
                return m
        # Final last-resort: the default model
        default = self._table.default_model()
        if default.model_id != primary.model_id:
            return default
        return None

    def _pick_escalation(
        self, candidates: list[ModelInfo], primary: ModelInfo
    ) -> Optional[ModelInfo]:
        """Pick a higher-quality alternative if the user escalates.

        Strategy (revised 2026-06-10): pick the best ACTIVE specialist,
        not Pro+. Pro+ models are listed in the routing table as
        "would-be-best if we had them" but aren't callable on the user's
        plan (they return "Model X is not supported" or 403). Pointing
        the cascade at a Pro+ model makes it fail every time. The
        cascade's "best" should be the best model the user can actually call.
        """
        # Prefer the best ACTIVE specialist (BEST_QUALITY > LONG_CONTEXT >
        # MULTIMODAL > DEFAULT) excluding the primary and the cheap workhorse.
        tier_order_active = {
            ModelTier.BEST_QUALITY: 0,
            ModelTier.LONG_CONTEXT: 1,
            ModelTier.MULTIMODAL: 2,
            ModelTier.LEGACY: 3,
            ModelTier.DEFAULT: 4,
            # CHEAP_WORKHORSE (5) and PRO_PLUS (6) intentionally excluded.
        }
        ranked = sorted(
            [
                m for m in candidates
                if m.model_id != primary.model_id
                and m.tier in tier_order_active
            ],
            key=lambda m: (
                tier_order_active.get(m.tier, 99),
                -(m.terminal_bench_score or 0),
            ),
        )
        if ranked:
            return ranked[0]
        # Final fallback: any candidate (including Pro+)
        for m in candidates:
            if m.model_id != primary.model_id:
                return m
        return None

    def _explain_choice(
        self,
        primary: ModelInfo,
        task_type: TaskType,
        budget: Optional[str],
    ) -> str:
        bits = [
            f"Task '{task_type.value}' → {primary.model_id} "
            f"on {primary.provider_name} (tier: {primary.tier.value})"
        ]
        if primary.terminal_bench_score:
            bits.append(f"TB: {primary.terminal_bench_score:.1f}%")
        if budget:
            bits.append(f"budget: {budget}")
        if primary.notes:
            bits.append(f"— {primary.notes}")
        return " · ".join(bits)
