"""Routing table — the static catalog of routable (provider, model) pairs.

This is the data-driven core of the router. Every model the agent can call is
listed here with metadata (cost, context, capabilities, tier). The selector
queries this table to find the best fit for a task type.

The data is ported from the model-router skill (active-pool-2026-06.md) and
model-catalog-2026-06.md. Refresh by re-probing the Kilo API (the skill has
the procedure). The intent is to keep the SKILL and the CODE in sync — any
divergence is a bug to fix.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TaskType(str, Enum):
    """Task categories the router recognizes.

    Keep this list short and unambiguous — each type has a known best-fit model
    in the routing table below. If a new task type emerges, add an enum value
    AND add its routing rule here.
    """

    # Coding tasks
    CODING_DEFAULT = "coding_default"          # general code work
    CODING_LONG_HORIZON = "coding_long_horizon"  # multi-step, agentic
    FRONTEND_UI = "frontend_ui"                  # UI/UX code generation

    # Reasoning / analysis
    REASONING = "reasoning"                      # math, logic, analysis
    CODE_REVIEW = "code_review"                  # reviewing existing code
    WRITING = "writing"                          # prose, copy, docs

    # Context size
    LONG_CONTEXT = "long_context"                # 200K+ tokens
    BULK_TRANSFORM = "bulk_transform"            # format work, simple Q&A
    CRON_BUDGET = "cron_budget"                  # budget-bounded background

    # Modalities
    VISION = "vision"                            # image input
    TRANSLATION = "translation"                  # multi-language

    # Catch-alls
    GENERAL = "general"                          # unknown / default
    ESCALATION = "escalation"                    # user explicitly wants best quality


class ModelTier(str, Enum):
    """Decision-first labels for what role a model plays in the active pool."""

    DEFAULT = "default"                  # the safe everyday pick
    BEST_QUALITY = "best_quality"        # highest TB score on Go plan
    CHEAP_WORKHORSE = "cheap_workhorse"  # 99% off, bulk use
    LONG_CONTEXT = "long_context"        # 1M token support
    MULTIMODAL = "multimodal"            # accepts image input
    LEGACY = "legacy"                    # superseded, kept for fallback only
    PRO_PLUS = "pro_plus"                # behind 403 on Go plan


class SubAgentRole(str, Enum):
    """Specialist roles for Aria sub-agents.

    Each role gets a model picked specifically for the kind of work it does.
    The mapping is data-driven via `ModelInfo.role_preferences`; the router
    picks the best active-pool model that claims the role.

    Roles:
    - PLANNER: design thinking, multi-step plans, decomposing tasks
    - ARCHITECT: high-level system design, broad thinking
    - IMPLEMENTER: write code, focused on output
    - DEBUGGER: find/fix bugs, logical analysis, root cause
    - DOCUMENTER: clear prose, structured documentation
    - REVIEWER: code review, quality checks, criticism
    - TESTER: edge-case generation, test design
    - VALIDATOR: correctness check, quality assessment
    - RESEARCHER: gather info, synthesize findings

    Sub-agents are how Aria "right tools for the job" — each role gets a
    specialist model. Parallel sub-agents run in parallel (asyncio.gather).
    Sequential sub-agents chain with context (planner → implementer → validator).
    """

    PLANNER = "planner"
    ARCHITECT = "architect"
    IMPLEMENTER = "implementer"
    DEBUGGER = "debugger"
    DOCUMENTER = "documenter"
    REVIEWER = "reviewer"
    TESTER = "tester"
    VALIDATOR = "validator"
    RESEARCHER = "researcher"


@dataclass(frozen=True)
class ModelInfo:
    """Static metadata about a routable model.

    Frozen so the routing table is effectively immutable; the registry resolves
    ModelInfo.provider_name → a live Provider instance at call time.
    """

    provider_name: str           # e.g. "opencode-go", "minimax-direct"
    model_id: str                # e.g. "kimi-k2.6", "MiniMax-M3"
    tier: ModelTier
    task_types: tuple[TaskType, ...]  # which task types this is a good fit for
    context_window: int = 0           # tokens
    cost_per_1m_input: float = 0.0    # USD
    cost_per_1m_output: float = 0.0   # USD
    terminal_bench_score: Optional[float] = None  # 0-100, if known
    accepts_images: bool = False
    notes: str = ""
    role_preferences: tuple[SubAgentRole, ...] = ()  # which sub-agent roles this is best for
    # Explicit provider-level fallback chain. When this model isn't callable
    # (e.g. its provider isn't registered in this environment), ProviderRegistry
    # walks these (provider_name, model_id) pairs in order until one is.
    #
    # Example: MiniMax-M3 on minimax-direct falls back to minimax-m3 on OCG
    # (the OCG mirror of M3 — same weights, different naming), then to
    # gpt-5.4-mini on Codex if both are unavailable.
    fallback_chain: tuple[tuple[str, str], ...] = ()

    def supports(self, task: TaskType) -> bool:
        return task in self.task_types

    def supports_role(self, role: SubAgentRole) -> bool:
        return role in self.role_preferences


# Active pool — verified on the Go plan as of 2026-06-10.
# Per the model-router skill, these are the models with confirmed 200 OK
# responses on the $1/mo Go plan.
#
# IMPORTANT — phantom-model discipline:
# A model is only listed here if `OpenCodeGoProvider.get_models()` or
# `MiniMaxProvider.get_models()` actually returns it. The provider's
# `get_models()` is the ground truth of what the live API can call. The
# routing table is a curated catalog, not a wishlist. Phantom models cause
# runtime errors on Termux (and anywhere) when the selector picks them and
# the provider can't serve them — resolved via `resolve_decision` in the
# registry, but the catalog itself should stay clean.
#
# Verified live OCG models (from opencode_go.py):
#   kimi-k2.5, kimi-k2.6, minimax-m2.5, minimax-m2.7, mimo-v2.5, mimo-v2.5-pro,
#   qwen-3.6-max, qwen-3.6-plus, qwen-3.7-plus, qwen-3.7-max,
#   nemotron-3-ultra-550b-a55b
# Verified live MiniMax-direct models (from minimax.py):
#   MiniMax-M3 (default), MiniMax-M2.7, MiniMax-M2.5, MiniMax-M2.1, MiniMax-M2
ACTIVE_POOL: list[ModelInfo] = [
    # --- minimax-direct: M3 (default session model, with fallback chain) ----
    # The fallback chain is the M3 user's explicit "go plan" preference:
    #   1. Primary: minimax-direct / MiniMax-M3 (direct, official)
    #   2. First fallback: zen / minimax-m3 (Zen mirror of M3 — verified
    #      live 2026-06-10: HTTP 200, lowercase-hyphen naming, same weights)
    #   3. Second fallback: openai-codex / gpt-5.4-mini (Codex OAuth route —
    #      not yet live on this plan, see Codex provider)
    #
    # The chain is consulted by ProviderRegistry.resolve_decision when the
    # primary's provider isn't registered. Verified live via probe: OCG serves
    # `minimax-m3` (lowercase-hyphen); MiniMax direct serves `MiniMax-M3`
    # (uppercase, mixed case). The case matters — they're DIFFERENT model
    # IDs on the wire, not just aliases.
    ModelInfo(
        provider_name="minimax-direct",
        model_id="MiniMax-M3",
        tier=ModelTier.DEFAULT,
        task_types=(
            TaskType.CODING_DEFAULT, TaskType.GENERAL, TaskType.WRITING,
            TaskType.VISION, TaskType.REASONING,
        ),
        context_window=1_048_576,
        cost_per_1m_input=0.30,
        cost_per_1m_output=1.20,
        terminal_bench_score=47.6,
        accepts_images=True,
        notes="Default session model. Native multimodal. Tolerant rate limits. "
              "On Termux with only OPENCODE_GO_API_KEY set, resolve_decision "
              "walks the fallback_chain to opencode-go/minimax-m3 (the OCG "
              "mirror, verified live 2026-06-10).",
        role_preferences=(
            SubAgentRole.IMPLEMENTER, SubAgentRole.TESTER, SubAgentRole.DOCUMENTER,
        ),
        fallback_chain=(
            ("zen", "minimax-m3"),    # 1st: OCG mirror of M3
            ("openai-codex", "gpt-5.4-mini"),  # 2nd: Codex OAuth route
        ),
    ),
    # --- opencode-go: kimi family (best quality, vision) ---------------
    ModelInfo(
        provider_name="opencode-go",
        model_id="kimi-k2.6",
        tier=ModelTier.BEST_QUALITY,
        task_types=(
            TaskType.CODING_LONG_HORIZON,
            TaskType.FRONTEND_UI, TaskType.CODE_REVIEW,
            TaskType.REASONING, TaskType.WRITING, TaskType.TRANSLATION,
            TaskType.VISION, TaskType.ESCALATION,
        ),
        context_window=262_144,
        cost_per_1m_input=0.80,
        cost_per_1m_output=3.40,
        terminal_bench_score=54.4,
        accepts_images=True,
        notes="Highest TB on Go plan. Vision-capable. UI/design work. "
              "The de-facto best-quality model on this plan (qwen/nemotron are Pro+).",
        role_preferences=(
            # All 9 specialist roles can use kimi — it's the only best-quality
            # model active on this plan. Specialists pick by role-tier ordering
            # in the selector, so a PLANNER picks kimi over a DEFAULT-tier
            # minimax-m2.7, while an IMPLEMENTER still picks m2.7 first.
            SubAgentRole.PLANNER, SubAgentRole.ARCHITECT, SubAgentRole.DOCUMENTER,
            SubAgentRole.REVIEWER, SubAgentRole.VALIDATOR,
            SubAgentRole.DEBUGGER, SubAgentRole.RESEARCHER,
        ),
    ),
    ModelInfo(
        provider_name="opencode-go",
        model_id="kimi-k2.5",
        tier=ModelTier.MULTIMODAL,
        task_types=(
            TaskType.FRONTEND_UI, TaskType.VISION, TaskType.LONG_CONTEXT,
        ),
        context_window=262_144,
        cost_per_1m_input=0.60,
        cost_per_1m_output=3.00,
        accepts_images=True,
        notes="Vision-capable. Frontend coding. 99% off promo.",
        role_preferences=(),  # Superseded by k2.6
    ),
    # --- zen: minimax-m3 (M3 mirror, verified live 2026-06-11) ---------
    # This is the OCG-served alias of MiniMax-M3. OCG uses lowercase-hyphen
    # naming (`minimax-m3`); MiniMax direct uses upper-mixed-case (`MiniMax-M3`).
    # They're different model IDs on the wire (not just aliases), but the
    # weights are the same. This entry exists so the registry can walk the
    # M3 chain: minimax-direct/MiniMax-M3 → opencode-go/minimax-m3.
    ModelInfo(
        provider_name="zen",
        model_id="minimax-m3",
        tier=ModelTier.DEFAULT,
        task_types=(
            TaskType.CODING_DEFAULT, TaskType.GENERAL, TaskType.WRITING,
            TaskType.VISION, TaskType.REASONING,
        ),
        context_window=1_048_576,
        cost_per_1m_input=0.30,
        cost_per_1m_output=1.20,
        terminal_bench_score=47.6,
        accepts_images=True,
        notes="M3 mirror on OCG (lowercase-hyphen naming, same weights). "
              "Verified live 2026-06-10 (HTTP 200). Used as the 1st fallback "
              "in MiniMax-M3's chain when minimax-direct isn't registered.",
        role_preferences=(),
        fallback_chain=(),  # The chain is on the canonical M3 entry (minimax-direct)
    ),
    # PRO+ on the user's Go plan — OCG lists these in its wider catalog
    # but the API returns "Model X is not supported" when called.
    # Kept here so the router knows they exist and can recommend plan upgrades.
    ModelInfo(
        provider_name="zen",
        model_id="qwen-3.7-max",
        tier=ModelTier.PRO_PLUS,
        task_types=(
            TaskType.CODING_LONG_HORIZON, TaskType.REASONING,
            TaskType.CODE_REVIEW, TaskType.ESCALATION,
        ),
        context_window=262_144,
        cost_per_1m_input=1.20,
        cost_per_1m_output=4.80,
        notes="Frontier coding+reasoning. PRO+ on this plan. "
              "Routed via Anthropic SDK (/zen/go base, x-api-key — see OCG provider).",
        role_preferences=(),  # Pro+ — not active on Go plan
    ),
    ModelInfo(
        provider_name="zen",
        model_id="qwen-3.7-plus",
        tier=ModelTier.PRO_PLUS,
        task_types=(
            TaskType.CODING_LONG_HORIZON, TaskType.REASONING,
            TaskType.WRITING, TaskType.ESCALATION,
        ),
        context_window=262_144,
        cost_per_1m_input=0.80,
        cost_per_1m_output=3.20,
        notes="Long-horizon coding. PRO+ on this plan. Sibling of qwen-3.7-max.",
        role_preferences=(),  # Pro+ — not active on Go plan
    ),
    # --- zen: qwen 3.6 (long-context, workhorse-quality) ---------------
    # PRO+ on the user's Go plan — see comment above.
    ModelInfo(
        provider_name="zen",
        model_id="qwen-3.6-max",
        tier=ModelTier.PRO_PLUS,
        task_types=(
            TaskType.LONG_CONTEXT, TaskType.CODE_REVIEW, TaskType.REASONING,
            TaskType.GENERAL,
        ),
        context_window=1_048_576,
        cost_per_1m_input=1.20,
        cost_per_1m_output=4.80,
        notes="1M context. Logical analysis, code review. PRO+ on this plan.",
        role_preferences=(),  # Pro+ — not active on Go plan
    ),
    ModelInfo(
        provider_name="zen",
        model_id="qwen-3.6-plus",
        tier=ModelTier.PRO_PLUS,
        task_types=(
            TaskType.LONG_CONTEXT, TaskType.GENERAL, TaskType.WRITING,
        ),
        context_window=1_048_576,
        cost_per_1m_input=0.60,
        cost_per_1m_output=2.40,
        notes="1M context. PRO+ on this plan. Sibling of qwen-3.6-max.",
        role_preferences=(),  # Pro+ — not active on Go plan
    ),
    # --- zen: MiniMax M2 (legacy direct models, mirrored) --------------
    ModelInfo(
        provider_name="zen",
        model_id="minimax-m2.7",
        tier=ModelTier.DEFAULT,
        task_types=(
            TaskType.CODING_DEFAULT, TaskType.GENERAL, TaskType.LONG_CONTEXT,
        ),
        context_window=1_048_576,
        cost_per_1m_input=0.30,
        cost_per_1m_output=1.20,
        notes="Mirrored on OCG. Default-tier. Multimodal. 1M context. "
              "Verified live OCG (probed 2026-06-10).",
        role_preferences=(SubAgentRole.IMPLEMENTER, SubAgentRole.TESTER),
    ),
    ModelInfo(
        provider_name="zen",
        model_id="minimax-m2.5",
        tier=ModelTier.MULTIMODAL,
        task_types=(TaskType.GENERAL, TaskType.VISION),
        context_window=1_048_576,
        cost_per_1m_input=0.20,
        cost_per_1m_output=1.00,
        notes="Mirrored on OCG. Cheaper than m2.7. Vision-capable. Verified live.",
        role_preferences=(),
    ),
    # --- opencode-go: nemotron 3 ultra (long-horizon reasoning) -------
    # PRO+ on the user's Go plan — see comment above.
    ModelInfo(
        provider_name="opencode-go",
        model_id="nemotron-3-ultra-550b-a55b",
        tier=ModelTier.PRO_PLUS,
        task_types=(
            TaskType.LONG_CONTEXT, TaskType.REASONING,
            TaskType.CODE_REVIEW, TaskType.GENERAL,
        ),
        context_window=1_048_576,
        cost_per_1m_input=2.00,
        cost_per_1m_output=6.00,
        notes="Long-horizon reasoning. 1M context. PRO+ on this plan. "
              "NVIDIA Nemotron 3 Ultra.",
        role_preferences=(),  # Pro+ — not active on Go plan
    ),
    # --- opencode-go: mimo (cheap workhorse) ---------------------------
    ModelInfo(
        provider_name="opencode-go",
        model_id="mimo-v2.5",
        tier=ModelTier.CHEAP_WORKHORSE,
        task_types=(
            TaskType.BULK_TRANSFORM, TaskType.CRON_BUDGET, TaskType.GENERAL,
        ),
        context_window=1_048_576,
        cost_per_1m_input=0.30,
        cost_per_1m_output=1.20,
        accepts_images=True,
        notes="99% off. 1M context. Default cheap workhorse. Cron/bulk use.",
        role_preferences=(),  # Cheap fallback; any role can use this if budget="cheap"
    ),
    ModelInfo(
        provider_name="opencode-go",
        model_id="mimo-v2.5-pro",
        tier=ModelTier.CHEAP_WORKHORSE,
        task_types=(TaskType.BULK_TRANSFORM, TaskType.GENERAL),
        context_window=1_048_576,
        cost_per_1m_input=0.50,
        cost_per_1m_output=1.50,
        notes="Slightly more capable than mimo-v2.5. Same 99% off promo.",
        role_preferences=(),
    ),
]


# Pro+ models — kept for routing context but blocked by 403 on the Go plan.
# Listed so the router knows they exist and can recommend plan upgrades.
PRO_PLUS_POOL: list[ModelInfo] = [
    ModelInfo(
        provider_name="openai-codex",
        model_id="gpt-5.4-mini",
        tier=ModelTier.PRO_PLUS,
        task_types=(
            TaskType.CODING_DEFAULT, TaskType.GENERAL,
        ),
        context_window=128_000,
        cost_per_1m_input=0.10,
        cost_per_1m_output=0.40,
        notes="Small/fast Codex model. M3 chain 2nd fallback "
              "(minimax-direct / MiniMax-M3 → opencode-go / minimax-m3 → "
              "openai-codex / gpt-5.4-mini). Pro+ on this plan — needs OAuth.",
    ),
    ModelInfo(
        provider_name="openai-codex",
        model_id="gpt-5.5",
        tier=ModelTier.PRO_PLUS,
        task_types=(
            TaskType.ESCALATION, TaskType.REASONING, TaskType.CODE_REVIEW,
        ),
        context_window=1_050_000,
        cost_per_1m_input=5.00,
        cost_per_1m_output=20.00,
        terminal_bench_score=74.2,
        notes="Frontier escalation target. Highest TB score. Pro+ only.",
    ),
]


class RoutingTable:
    """The complete catalog of routable models + decision rules.

    Built from ACTIVE_POOL and PRO_PLUS_POOL by default. Use the lookup methods
    to find models by ID, by task type, or by tier.
    """

    def __init__(self, models: Optional[list[ModelInfo]] = None):
        self._models: list[ModelInfo] = list(models) if models is not None else (
            list(ACTIVE_POOL) + list(PRO_PLUS_POOL)
        )
        # Index by (provider, model_id) for O(1) lookup.
        self._index: dict[tuple[str, str], ModelInfo] = {
            (m.provider_name, m.model_id): m for m in self._models
        }

    def all(self) -> list[ModelInfo]:
        return list(self._models)

    def get(self, provider_name: str, model_id: str) -> Optional[ModelInfo]:
        return self._index.get((provider_name, model_id))

    def find_by_model_id(self, model_id: str) -> list[ModelInfo]:
        """Return all entries for a model_id across providers."""
        return [m for m in self._models if m.model_id == model_id]

    def find_by_task(self, task: TaskType) -> list[ModelInfo]:
        """Return all models that claim to handle this task, ordered by tier.

        Ordering rules:
        1. Specialist tiers (BEST_QUALITY, LONG_CONTEXT, MULTIMODAL) come BEFORE the
           catch-all DEFAULT tier for specialized tasks. M3 is the right answer for
           GENERAL queries but should not beat Kimi/DeepSeek on REASONING/LONG_CONTEXT.
        2. Within a tier, models with higher TB score come first.
        3. PRO_PLUS always last (blocked on Go plan).
        """
        # Tier order: specialists (1-3) before generalists (4-5)
        tier_order = {
            ModelTier.BEST_QUALITY: 0,
            ModelTier.LONG_CONTEXT: 1,
            ModelTier.MULTIMODAL: 2,
            ModelTier.LEGACY: 3,
            ModelTier.DEFAULT: 4,
            ModelTier.CHEAP_WORKHORSE: 5,
            ModelTier.PRO_PLUS: 6,
        }
        candidates = [m for m in self._models if m.supports(task)]
        candidates.sort(
            key=lambda m: (
                tier_order.get(m.tier, 99),
                -(m.terminal_bench_score or 0),
            )
        )
        return candidates

    def find_by_role(self, role: SubAgentRole) -> list[ModelInfo]:
        """Return all models that claim this sub-agent role, ordered by tier.

        Same ordering rules as `find_by_task`: specialists (BEST_QUALITY,
        LONG_CONTEXT) before generalists (DEFAULT, CHEAP_WORKHORSE). Within
        a tier, higher TB score wins. PRO_PLUS last.

        Models without `role_preferences` for this role are excluded — they
        haven't claimed to be a good fit for this kind of work. The cheap
        workhorse is intentionally NOT in role_preferences because it's the
        fallback for any role when `budget="cheap"`.
        """
        tier_order = {
            ModelTier.BEST_QUALITY: 0,
            ModelTier.LONG_CONTEXT: 1,
            ModelTier.MULTIMODAL: 2,
            ModelTier.LEGACY: 3,
            ModelTier.DEFAULT: 4,
            ModelTier.CHEAP_WORKHORSE: 5,
            ModelTier.PRO_PLUS: 6,
        }
        candidates = [m for m in self._models if m.supports_role(role)]
        candidates.sort(
            key=lambda m: (
                tier_order.get(m.tier, 99),
                -(m.terminal_bench_score or 0),
            )
        )
        return candidates

    def active_pool(self) -> list[ModelInfo]:
        """Return only the Go-plan-verified models."""
        return [m for m in self._models if m.tier != ModelTier.PRO_PLUS]

    def cheap_pool(self) -> list[ModelInfo]:
        """Return models in the cheap-workhorse tier."""
        return [m for m in self._models if m.tier == ModelTier.CHEAP_WORKHORSE]

    def default_model(self) -> ModelInfo:
        """Return the default session model (M3)."""
        for m in self._models:
            if m.tier == ModelTier.DEFAULT:
                return m
        raise LookupError("No default model configured in routing table")


_default_table: Optional[RoutingTable] = None


def get_default_routing_table() -> RoutingTable:
    """Return the process-wide default routing table."""
    global _default_table
    if _default_table is None:
        _default_table = RoutingTable()
    return _default_table


def reset_default_routing_table() -> None:
    """Reset for testing."""
    global _default_table
    _default_table = None
