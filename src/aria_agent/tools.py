from typing import Any, Callable, Dict, List

from pydantic import BaseModel

from .builtin_tools.calculator import CalculatorInput, calculator
from .builtin_tools.email_draft import EmailDraftInput, email_draft
from .builtin_tools.file_reader import FileReaderInput, file_reader
from .builtin_tools.task_creator import TaskCreatorInput, task_creator
from .builtin_tools.web_search import WebSearchInput, web_search


class ToolRegistry:
    """Manages active tool definitions and parameter schemas."""

    def __init__(self):
        self.tools: Dict[str, Callable] = {}
        self.schemas: Dict[str, type[BaseModel]] = {}

    def register(self, name: str, schema: type[BaseModel]):
        def decorator(func: Callable):
            self.tools[name] = func
            self.schemas[name] = schema
            return func

        return decorator

    def call_tool(self, name: str, args: Dict[str, Any]) -> Any:
        if name not in self.tools:
            raise KeyError(f"Tool {name} not found.")
        schema = self.schemas[name]
        validated_args = schema(**args)
        return self.tools[name](**validated_args.model_dump())

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": name,
                "schema": schema.model_json_schema(),
            }
            for name, schema in self.schemas.items()
        ]

    def get_schema(self, name: str) -> Dict[str, Any]:
        if name not in self.schemas:
            raise KeyError(f"Tool {name} not found.")
        return self.schemas[name].model_json_schema()


__all__ = [
    "ToolRegistry",
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
