"""SubAgentRegistry — role → SubAgent catalog.

The registry holds a SubAgent for each role. By default, it builds one
sub-agent per role using the default role spec + the router. Callers can
register custom sub-agents (with different specs, models, or system
prompts) to override the default.

Usage:
    registry = SubAgentRegistry(provider_registry, router)
    planner = registry.get(SubAgentRole.PLANNER)
    result = await planner.run("Add a /health endpoint")

    # Or register a custom sub-agent
    registry.register(SubAgentRole.PLANNER, SubAgent(
        role=SubAgentRole.PLANNER,
        registry=provider_registry,
        router=router,
        spec=SubAgentRoleSpec(
            role=SubAgentRole.PLANNER,
            system_prompt="You are a minimal planner. Just list 3 steps.",
            temperature=0.3,
            max_tokens=512,
        ),
    ))
"""
from typing import Optional

from ..providers.registry import ProviderRegistry
from ..router.routing_table import SubAgentRole
from .base import DEFAULT_ROLE_SPECS, SubAgent, SubAgentRoleSpec


class SubAgentRegistry:
    """Maps roles to SubAgent instances.

    Defaults: one sub-agent per role, using `DEFAULT_ROLE_SPECS` and
    the router. Override per-role via `register(role, agent)`.

    Per-request state: this is the SHARED registry. Sub-agents themselves
    are stateless (their state is the model + spec, not request data).
    The Orchestrator creates per-request context (memory, results history).
    """

    def __init__(
        self,
        registry: ProviderRegistry,
        router,
        *,
        specs: Optional[dict[SubAgentRole, SubAgentRoleSpec]] = None,
    ):
        self._registry = registry
        self._router = router
        # Sub-agents are built lazily (first call to get()) so the registry
        # doesn't construct 9 sub-agents at startup if only 2 are ever used.
        self._agents: dict[SubAgentRole, SubAgent] = {}
        # Custom specs override the defaults
        self._custom_specs: dict[SubAgentRole, SubAgentRoleSpec] = specs or {}

    def get(self, role: SubAgentRole) -> SubAgent:
        """Get the SubAgent for a role. Lazy-builds on first call."""
        if role not in self._agents:
            spec = self._custom_specs.get(role) or DEFAULT_ROLE_SPECS[role]
            self._agents[role] = SubAgent(
                role=role,
                registry=self._registry,
                router=self._router,
                spec=spec,
            )
        return self._agents[role]

    def register(self, role: SubAgentRole, agent: SubAgent) -> None:
        """Register a custom SubAgent for a role. Overrides the default."""
        self._agents[role] = agent

    def register_spec(self, role: SubAgentRole, spec: SubAgentRoleSpec) -> None:
        """Register a custom role spec. Used on next lazy-build for this role."""
        self._custom_specs[role] = spec
        # Invalidate any cached agent so the new spec takes effect
        self._agents.pop(role, None)

    def list_roles(self) -> list[SubAgentRole]:
        """List all roles this registry can produce sub-agents for."""
        return list(SubAgentRole)

    def has_role(self, role: SubAgentRole) -> bool:
        return role in SubAgentRole

    def get_spec(self, role: SubAgentRole) -> SubAgentRoleSpec:
        """Return the spec for a role (default or custom)."""
        return self._custom_specs.get(role) or DEFAULT_ROLE_SPECS[role]


_default_registry: Optional["SubAgentRegistry"] = None


def get_default_sub_agent_registry(
    provider_registry: Optional[ProviderRegistry] = None,
    router=None,
) -> SubAgentRegistry:
    """Return the process-wide default sub-agent registry.

    If provider_registry or router are not provided, the default ones are
    fetched. The registry is built lazily on first call.
    """
    global _default_registry
    if _default_registry is None:
        if provider_registry is None:
            from ..providers.registry import get_default_registry
            provider_registry = get_default_registry()
        if router is None:
            from ..router.selector import ModelSelector
            from ..router.routing_table import get_default_routing_table
            router = ModelSelector(get_default_routing_table())
        _default_registry = SubAgentRegistry(provider_registry, router)
    return _default_registry


def reset_default_sub_agent_registry() -> None:
    """Reset for testing."""
    global _default_registry
    _default_registry = None
