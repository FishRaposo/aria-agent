"""Aria Agent — cross-provider model router with cooperation patterns.

A FastAPI service that picks the best model for a task across multiple
providers (OpenCode Go, MiniMax direct, OpenAI Codex) and orchestrates
cooperation patterns (cascade, plan-execute-validate, ensemble) when a
task benefits from multiple models working together.

**v0.3 unifies v0.1 and v0.2:**

- v0.1: tool-calling agent (KeywordRouterAgent) with calculator, web_search,
  file_reader, task_creator, email_draft. Preserved verbatim.
- v0.2: cross-provider model router with cascade/plan-execute/ensemble
  cooperation patterns. Preserved verbatim.
- v0.3: a single AriaAgent orchestrator that picks the right path
  automatically (tool vs model) and exposes a uniform API surface.

**Public API:**

- AriaAgent — the central orchestrator (v0.3)
- KeywordRouterAgent — the v0.1 tool agent (preserved)
- ToolRegistry, ApprovalGate, AgentMemory, CostTracker, TraceLog — v0.1
  components, all still available
- builtin_tools — calculator, web_search, file_reader, task_creator,
  email_draft (v0.1, all preserved)
- ProviderRegistry, BaseProvider, MiniMaxProvider, etc. — v0.2 providers
- ModelSelector, RoutingTable, TaskType, ModelInfo — v0.2 router
- CooperationPattern, CascadePattern, etc. — v0.2 cooperation patterns
"""
__version__ = "0.4.0"

# Agent (v0.3 orchestrator + v0.1 preserved)
from .agent import AriaAgent, Intent, IntentClassification
from .agents import KeywordRouterAgent, AriaAgent as _LegacyAriaAgentAlias

# v0.1 components (preserved)
from .approvals import ApprovalGate
from .costs import CostTracker
from .memory import AgentMemory
from .tools import ToolRegistry
from .tracing import TraceLog

# v0.1 builtin tools (preserved)
from . import builtin_tools
from .builtin_tools import (
    CalculatorInput,
    EmailDraftInput,
    FileReaderInput,
    TaskCreatorInput,
    WebSearchInput,
    calculator,
    email_draft,
    file_reader,
    task_creator,
    web_search,
)

# v0.2 components
from .cooperation import (
    CascadePattern,
    CooperationPattern,
    CooperationResult,
    EnsemblePattern,
    PlanExecuteValidatePattern,
    QualityAssessment,
    StepResult,
    assess_quality,
)
from .config import AppConfig
from .providers import (
    BaseProvider,
    MiniMaxProvider,
    OpenAICodexProvider,
    OpenCodeGoProvider,
    ProviderError,
    ProviderRegistry,
    get_default_registry,
)
from .router import (
    ModelInfo,
    ModelSelector,
    RoutingDecision,
    RoutingTable,
    SubAgentRole,
    TaskClassifier,
    TaskType,
    get_default_routing_table,
)
# v0.4 sub-agent system
from .subagents import (
    OrchestrationResult,
    OrchestrationStep,
    Orchestrator,
    SubAgent,
    SubAgentRegistry,
    SubAgentResult,
    SubAgentRoleSpec,
    build_default_sub_agent,
    get_default_sub_agent_registry,
)


__all__ = [
    # Version
    "__version__",
    # Agent (v0.3)
    "AriaAgent",
    "Intent",
    "IntentClassification",
    # v0.1 preserved
    "KeywordRouterAgent",
    "_LegacyAriaAgentAlias",  # backwards-compat alias
    "ApprovalGate",
    "AgentMemory",
    "CostTracker",
    "TraceLog",
    "ToolRegistry",
    # v0.1 builtin tools
    "builtin_tools",
    "CalculatorInput", "EmailDraftInput", "FileReaderInput",
    "TaskCreatorInput", "WebSearchInput",
    "calculator", "email_draft", "file_reader",
    "task_creator", "web_search",
    # v0.2 cooperation
    "CascadePattern",
    "CooperationPattern",
    "CooperationResult",
    "EnsemblePattern",
    "PlanExecuteValidatePattern",
    "QualityAssessment",
    "StepResult",
    "assess_quality",
    # v0.2 config
    "AppConfig",
    # v0.2 providers
    "BaseProvider",
    "MiniMaxProvider",
    "OpenAICodexProvider",
    "OpenCodeGoProvider",
    "ProviderError",
    "ProviderRegistry",
    "get_default_registry",
    # v0.2 router
    "ModelInfo",
    "ModelSelector",
    "RoutingDecision",
    "RoutingTable",
    "SubAgentRole",
    "TaskClassifier",
    "TaskType",
    "get_default_routing_table",
    # v0.4 sub-agents
    "SubAgent",
    "SubAgentRegistry",
    "SubAgentResult",
    "SubAgentRoleSpec",
    "build_default_sub_agent",
    "get_default_sub_agent_registry",
    "Orchestrator",
    "OrchestrationResult",
    "OrchestrationStep",
]
