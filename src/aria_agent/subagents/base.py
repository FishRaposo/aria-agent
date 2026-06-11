"""Sub-agent base classes + role system prompts.

A `SubAgent` is a single-role worker. The router picks the model based on
`ModelInfo.role_preferences`. The agent calls the model via the provider
layer, then returns a structured `SubAgentResult`.

Each role has a system prompt that primes the model for the kind of work
it does. These are intentionally short and focused — the user's task
provides the actual content.
"""
from dataclasses import dataclass, field
from typing import Optional

from ..providers.base import ProviderError
from ..providers.registry import ProviderRegistry
from ..router.routing_table import SubAgentRole


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass
class SubAgentResult:
    """Structured result of a single sub-agent run.

    Records which role ran, which model was used, what came back, and how
    it performed. Used by the orchestrator to show the user what happened
    and to chain outputs together.
    """

    role: SubAgentRole
    model_id: str
    provider_name: str
    output_text: str
    input_messages: list[dict] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    success: bool = True
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


# ---------------------------------------------------------------------------
# Role spec — config that defines a sub-agent's behavior
# ---------------------------------------------------------------------------

@dataclass
class SubAgentRoleSpec:
    """Static config for a sub-agent role.

    Defines the system prompt, default temperature, and max_tokens for a
    role. Model selection is data-driven via `ModelInfo.role_preferences`
    in the routing table — the spec doesn't pin a model. The user can
    override per-call via `SubAgent(model_id=...)`.

    Attributes:
        role: The sub-agent role
        system_prompt: Template primed for this role (e.g., "You are a
            planner. Decompose the user's request into ordered steps...")
        temperature: Default sampling temperature (0.0 = deterministic,
            1.0 = creative). 0.7 is a good default for most roles.
        max_tokens: Default max output tokens. 2048 fits most responses;
            increase for code-heavy roles.
        description: One-line description of what this role does
    """

    role: SubAgentRole
    system_prompt: str
    temperature: float = 0.7
    max_tokens: int = 2048
    description: str = ""


# ---------------------------------------------------------------------------
# System prompts per role
# ---------------------------------------------------------------------------

SYSTEM_PROMPTS: dict[SubAgentRole, str] = {
    SubAgentRole.PLANNER: (
        "You are a planning specialist. Your job is to break down the user's "
        "request into clear, ordered, actionable steps. For each step, specify:\n"
        "- What the step produces (concrete deliverable)\n"
        "- What tools/skills are needed (if any)\n"
        "- Dependencies on prior steps\n"
        "Be concrete. Avoid vague steps like 'research' or 'design' — say "
        "what specifically gets researched, what gets designed. Output a "
        "structured plan that another agent can execute."
    ),
    SubAgentRole.ARCHITECT: (
        "You are a software architecture specialist. Your job is to produce "
        "high-level system designs: components, their responsibilities, "
        "interfaces, data flow, and trade-offs. Focus on:\n"
        "- Component boundaries (what each piece owns)\n"
        "- Data flow (how information moves between components)\n"
        "- Failure modes (what can go wrong, how to handle it)\n"
        "- Trade-offs (why this design over alternatives)\n"
        "Be specific. Name the components, the data structures, the protocols. "
        "Output should be detailed enough that an implementer can build it."
    ),
    SubAgentRole.IMPLEMENTER: (
        "You are a software implementation specialist. Your job is to write "
        "production-quality code that follows the user's spec exactly. Focus on:\n"
        "- Correctness (the code must work as specified)\n"
        "- Clarity (the code should be readable)\n"
        "- Defensive coding (handle edge cases, validate inputs)\n"
        "- Idiomatic style (match the language's conventions)\n"
        "Output the full implementation, not pseudocode. Include necessary "
        "imports, type hints, and error handling."
    ),
    SubAgentRole.DEBUGGER: (
        "You are a debugging specialist. Your job is to find and fix the root "
        "cause of bugs. Approach:\n"
        "1. Read the symptoms (what's failing, what error, what input)\n"
        "2. Form hypotheses about root cause\n"
        "3. For each hypothesis, identify the smallest test that confirms/refutes it\n"
        "4. Once confirmed, propose a fix\n"
        "5. Verify the fix doesn't break related code\n"
        "Be specific: name the file, the line, the function. Explain WHY "
        "the bug exists, not just WHAT to change."
    ),
    SubAgentRole.DOCUMENTER: (
        "You are a technical documentation specialist. Your job is to write "
        "clear, well-structured documentation. Focus on:\n"
        "- Audience (who is reading this? developers? users? both?)\n"
        "- Structure (use headers, lists, code blocks as appropriate)\n"
        "- Examples (concrete, runnable code or commands)\n"
        "- Conciseness (every word earns its place)\n"
        "Output should be ready to drop into a README, doc page, or inline "
        "docstring. Avoid marketing language."
    ),
    SubAgentRole.REVIEWER: (
        "You are a code review specialist. Your job is to critically review "
        "code for correctness, quality, and maintainability. Look for:\n"
        "- Bugs (off-by-one, edge cases, race conditions)\n"
        "- Security issues (input validation, auth, secrets)\n"
        "- Performance (unnecessary work, N+1, blocking I/O)\n"
        "- Maintainability (clarity, naming, testability)\n"
        "Be direct. Point out specific lines. Suggest concrete improvements. "
        "If the code is good, say so — don't invent issues."
    ),
    SubAgentRole.TESTER: (
        "You are a testing specialist. Your job is to design tests that catch "
        "real bugs. Focus on:\n"
        "- Edge cases (empty input, max values, unicode, null)\n"
        "- Error paths (invalid input, network failure, timeout)\n"
        "- Boundary conditions (off-by-one, empty, exactly-at-limit)\n"
        "- Integration points (where this meets the rest of the system)\n"
        "Output concrete, runnable test code with clear names that document "
        "the scenario. Avoid tautological tests (test that x == x)."
    ),
    SubAgentRole.VALIDATOR: (
        "You are a validation specialist. Your job is to check whether an "
        "output meets a specification. Be specific:\n"
        "- Does the output match the spec? (yes/no, with evidence)\n"
        "- Are there edge cases the spec missed?\n"
        "- Is the output correct, complete, consistent?\n"
        "- If issues exist, what specifically is wrong?\n"
        "Output a clear verdict (PASS / FAIL / NEEDS_REVISION) with a "
        "concrete list of issues. Don't hedge."
    ),
    SubAgentRole.RESEARCHER: (
        "You are a research specialist. Your job is to gather and synthesize "
        "information. Approach:\n"
        "1. Identify what the user needs to know\n"
        "2. List the key questions to answer\n"
        "3. Synthesize what's known (cite sources if possible)\n"
        "4. Identify gaps (what's NOT known)\n"
        "5. Recommend next steps (where to look for answers)\n"
        "Output should be a structured briefing, not a wall of text. "
        "Use headers, bullet points, and citations."
    ),
}


DEFAULT_ROLE_SPECS: dict[SubAgentRole, SubAgentRoleSpec] = {
    role: SubAgentRoleSpec(
        role=role,
        system_prompt=prompt,
        temperature=0.7 if role in (SubAgentRole.DOCUMENTER, SubAgentRole.RESEARCHER) else 0.4,
        max_tokens=4096 if role in (SubAgentRole.IMPLEMENTER, SubAgentRole.ARCHITECT) else 2048,
        description=prompt.split(".")[0] + ".",  # First sentence
    )
    for role, prompt in SYSTEM_PROMPTS.items()
}


# ---------------------------------------------------------------------------
# SubAgent — single-role worker
# ---------------------------------------------------------------------------

class SubAgent:
    """A specialized worker with a role and a role-picked model.

    Lifecycle:
    1. Constructed with a role, registry, router, and an optional model
       override. The router picks the model based on the role's
       `role_preferences` in the routing table.
    2. `await sub_agent.run(task)` makes a single LLM call.
    3. Returns a `SubAgentResult` with full metadata.

    The SubAgent is intentionally simple — one model call, one result.
    Coordination, parallelism, and chaining are the Orchestrator's job
    (in `orchestrator.py`).

    Args:
        role: Which sub-agent role this is (planner, implementer, etc.)
        registry: ProviderRegistry for resolving (provider, model) → live client
        router: ModelSelector for picking the best model for the role
        spec: Optional role spec (defaults to DEFAULT_ROLE_SPECS[role])
        model_id: Optional explicit model override. If set, this model is
                 used regardless of role preferences (useful for testing
                 or when the caller knows the best model for the job).

    Example:
        sub = SubAgent(SubAgentRole.PLANNER, registry, router)
        result = await sub.run("Add a /health endpoint to the FastAPI app")
        # result.model_id == "kimi-k2.6" (picked for planner role)
    """

    def __init__(
        self,
        role: SubAgentRole,
        registry: ProviderRegistry,
        router,
        *,
        spec: Optional[SubAgentRoleSpec] = None,
        model_id: Optional[str] = None,
    ):
        self.role = role
        self.registry = registry
        self.router = router
        self.spec = spec or DEFAULT_ROLE_SPECS[role]
        self.model_id_override = model_id

    def pick_model(self) -> tuple[str, str]:
        """Pick the model for this role. Returns (provider_name, model_id).

        If `model_id_override` is set, use that and resolve the provider.
        Otherwise, ask the router to pick via `select_for_role` and then
        resolve through the registry — the registry knows what's actually
        registered, and falls back through the decision's chain to the
        routing table's defaults if the preferred provider isn't available.

        This is what makes the SubAgent work in environments where only a
        subset of providers are configured (e.g. Termux with only the OCG
        key: the implementer role prefers minimax-direct/M3, but that
        provider isn't registered, so the registry falls back through the
        decision chain to OCG/M3 → cheap workhorse).
        """
        if self.model_id_override is not None:
            # Use the override; resolve provider via public API
            if not self.registry.has_model(self.model_id_override):
                raise KeyError(
                    f"Model '{self.model_id_override}' not served by any "
                    f"registered provider. "
                    f"Available: {self.registry.list_providers()}"
                )
            name, _ = self.registry.resolve_model(self.model_id_override)
            return name, self.model_id_override

        decision = self.router.select_for_role(self.role)
        # The registry walks primary → fallback → escalation → table defaults,
        # so we get a callable model even if the preferred one isn't registered.
        return self.registry.resolve_decision(decision)

    async def run(self, task: str, *, context: Optional[str] = None) -> SubAgentResult:
        """Run the sub-agent on a task.

        Args:
            task: The user's request (free-form text)
            context: Optional prior context to prepend (used by Orchestrator
                when chaining sub-agents in sequence)

        Returns:
            SubAgentResult with model_id, provider, output, cost, latency.

        Raises:
            ProviderError: if the model call fails (auth, network, etc.)
        """
        provider_name, model_id = self.pick_model()
        provider = self.registry.get(provider_name)

        messages: list[dict] = []
        # System prompt (role-specific)
        messages.append({"role": "system", "content": self.spec.system_prompt})
        # Optional context from prior sub-agents (sequential chaining)
        if context:
            messages.append({
                "role": "system",
                "content": f"Prior context from earlier sub-agents:\n\n{context}",
            })
        # The actual task
        messages.append({"role": "user", "content": task})

        try:
            response = await provider.chat(
                model=model_id,
                messages=messages,
                temperature=self.spec.temperature,
                max_tokens=self.spec.max_tokens,
            )
            return SubAgentResult(
                role=self.role,
                model_id=model_id,
                provider_name=provider_name,
                output_text=response.text,
                input_messages=messages,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                latency_ms=response.latency_ms,
                cost_usd=response.estimated_cost,
                success=True,
                metadata={"picked_via": "router" if self.model_id_override is None else "override"},
            )
        except ProviderError as e:
            return SubAgentResult(
                role=self.role,
                model_id=model_id,
                provider_name=provider_name,
                output_text="",
                input_messages=messages,
                success=False,
                error=str(e),
                metadata={"picked_via": "router" if self.model_id_override is None else "override"},
            )


def build_default_sub_agent(
    role: SubAgentRole,
    registry: ProviderRegistry,
    router,
    *,
    model_id: Optional[str] = None,
) -> SubAgent:
    """Convenience: build a SubAgent with the default spec for a role.

    Equivalent to `SubAgent(role, registry, router, model_id=model_id)`.
    """
    return SubAgent(role, registry, router, model_id=model_id)
