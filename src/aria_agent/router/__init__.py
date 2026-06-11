"""Router layer for Aria Agent.

The router is the brain of the new direction: it picks the best (provider, model)
pair for a given task, based on rules ported from the model-router skill.

Components:
- `routing_table.py`: catalog of routable models with metadata + decision rules
- `classifier.py`: classify a free-form task into a TaskType (rule-based v1)
- `selector.py`: pick the best model for a TaskType using the routing table

The router does NOT make API calls — it just decides. The agent (in
`aria_agent.agent`) is the one that actually calls providers.
"""
from .routing_table import (
    SubAgentRole,
    TaskType,
    ModelInfo,
    RoutingTable,
    get_default_routing_table,
)
from .classifier import TaskClassifier
from .selector import ModelSelector, RoutingDecision

__all__ = [
    "SubAgentRole",
    "TaskType",
    "ModelInfo",
    "RoutingTable",
    "get_default_routing_table",
    "TaskClassifier",
    "ModelSelector",
    "RoutingDecision",
]
