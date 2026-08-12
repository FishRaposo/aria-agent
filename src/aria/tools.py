"""ARIA tool registry with Pydantic-validated schemas and permission levels.

Each registered tool carries a permission level: ``SAFE`` tools execute directly,
``REQUIRES_APPROVAL`` tools are routed through the approval queue before execution
when the agent runs in approval-gated mode. Arguments are validated against the
tool's Pydantic schema in ``call_tool`` *before* the function runs, so a tool
never sees malformed input.
"""

from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel

from .builtin_tools.calculator import CalculatorInput, calculator
from .builtin_tools.email_draft import EmailDraftInput, email_draft
from .builtin_tools.file_reader import FileReaderInput, file_reader
from .builtin_tools.task_creator import (
    TaskCreatorInput,
    make_task_creator,
    task_creator,
)
from .builtin_tools.web_search import WebSearchInput, web_search


class Permission(str, Enum):
    """Permission level controlling whether a tool needs human approval."""

    SAFE = "safe"
    REQUIRES_APPROVAL = "requires_approval"


class ToolSpec(BaseModel):
    """Public description of a registered tool."""

    name: str
    permission: Permission
    description: str = ""
    json_schema: Dict[str, Any] = {}

    model_config = {"use_enum_values": True}


class ToolRegistry:
    """Manages active tool definitions, schemas, and permission levels."""

    def __init__(self) -> None:
        self.tools: Dict[str, Callable] = {}
        self.schemas: Dict[str, type[BaseModel]] = {}
        self.permissions: Dict[str, Permission] = {}
        self.descriptions: Dict[str, str] = {}

    def register(
        self,
        name: str,
        schema: type[BaseModel],
        permission: Permission = Permission.SAFE,
        description: str = "",
    ):
        def decorator(func: Callable) -> Callable:
            self.tools[name] = func
            self.schemas[name] = schema
            self.permissions[name] = permission
            self.descriptions[name] = description or (func.__doc__ or "").strip()
            return func

        return decorator

    def add(
        self,
        name: str,
        schema: type[BaseModel],
        func: Callable,
        permission: Permission = Permission.SAFE,
        description: str = "",
    ) -> None:
        """Imperative registration (non-decorator) for builtin tools."""
        self.register(name, schema, permission, description)(func)

    def call_tool(self, name: str, args: Dict[str, Any]) -> Any:
        if name not in self.tools:
            raise KeyError(f"Tool {name} not found.")
        schema = self.schemas[name]
        validated_args = schema(**args)
        return self.tools[name](**validated_args.model_dump())

    def permission_for(self, name: str) -> Permission:
        if name not in self.permissions:
            raise KeyError(f"Tool {name} not found.")
        return self.permissions[name]

    def requires_approval(self, name: str) -> bool:
        return self.permission_for(name) == Permission.REQUIRES_APPROVAL

    def names(self) -> List[str]:
        return list(self.tools.keys())

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": name,
                "permission": self.permissions[name].value,
                "description": self.descriptions.get(name, ""),
                "schema": schema.model_json_schema(),
            }
            for name, schema in self.schemas.items()
        ]

    def get_schema(self, name: str) -> Dict[str, Any]:
        if name not in self.schemas:
            raise KeyError(f"Tool {name} not found.")
        return self.schemas[name].model_json_schema()


def build_default_registry(task_store: Optional[Any] = None) -> ToolRegistry:
    """Register the five builtin tools with appropriate permission levels.

    ``task_creator`` persists into ``task_store`` when provided; ``email_draft``
    requires approval (it produces an outbound artifact, even though it never
    sends), all others are safe read-only/compute tools.
    """
    registry = ToolRegistry()
    registry.add(
        "calculator",
        CalculatorInput,
        calculator,
        Permission.SAFE,
        "Safely evaluate an arithmetic expression (AST-based, no eval).",
    )
    registry.add(
        "web_search",
        WebSearchInput,
        web_search,
        Permission.SAFE,
        "Search the web (real when configured, deterministic mock offline).",
    )
    registry.add(
        "file_reader",
        FileReaderInput,
        file_reader,
        Permission.SAFE,
        "Read a text file from the sandboxed, allowlisted directory.",
    )
    creator = make_task_creator(task_store) if task_store is not None else task_creator
    registry.add(
        "task_creator",
        TaskCreatorInput,
        creator,
        Permission.REQUIRES_APPROVAL,
        "Persist a new task (write action — requires approval).",
    )
    registry.add(
        "email_draft",
        EmailDraftInput,
        email_draft,
        Permission.REQUIRES_APPROVAL,
        "Draft a structured email — never sends (requires approval).",
    )
    return registry


__all__ = [
    "ToolRegistry",
    "ToolSpec",
    "Permission",
    "build_default_registry",
    "calculator",
    "email_draft",
    "file_reader",
    "task_creator",
    "web_search",
    "CalculatorInput",
    "EmailDraftInput",
    "FileReaderInput",
    "TaskCreatorInput",
    "WebSearchInput",
]
