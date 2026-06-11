"""Sub-agents — specialized workers with role-specific model delegation.

A sub-agent is a worker that:
1. Has a specific ROLE (planner, architect, implementer, debugger, etc.)
2. Uses a model picked for that role (via the routing table's role_preferences)
3. Returns a structured `SubAgentResult` with full cost/latency/model info

Sub-agents are how Aria does "right tool for the job":
- planner → kimi-k2.6 (best for deep reasoning)
- architect → kimi-k2.6 (broad design thinking)
- implementer → MiniMax-M3 (default, native coding)
- debugger → deepseek-v4-pro (long context, logical analysis)
- documenter → kimi-k2.6 or MiniMax-M3 (writing quality)
- reviewer → glm-5.1 (multi-mode thinking, code review)
- tester → MiniMax-M3 (default, edge-case generation)
- validator → glm-5.1 (multi-mode, correctness checks)
- researcher → deepseek-v4-pro (long context, synthesis)

The `Orchestrator` (in `orchestrator.py`) runs sub-agents in parallel
(asyncio.gather) or sequentially (chain with context). This is the
"parallelization wherever it makes sense" piece.
"""
from .base import (
    DEFAULT_ROLE_SPECS,
    SubAgent,
    SubAgentResult,
    SubAgentRoleSpec,
    SYSTEM_PROMPTS,
    build_default_sub_agent,
)
from .registry import SubAgentRegistry, get_default_sub_agent_registry
from .orchestrator import Orchestrator, OrchestrationResult, OrchestrationStep


__all__ = [
    "SubAgent",
    "SubAgentResult",
    "SubAgentRoleSpec",
    "DEFAULT_ROLE_SPECS",
    "SYSTEM_PROMPTS",
    "build_default_sub_agent",
    "SubAgentRegistry",
    "get_default_sub_agent_registry",
    "Orchestrator",
    "OrchestrationResult",
    "OrchestrationStep",
]
