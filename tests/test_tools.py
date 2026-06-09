import pytest
from hermes.tools import ToolRegistry
from pydantic import BaseModel


class CalculatorInput(BaseModel):
    expression: str


class GreetInput(BaseModel):
    name: str


@pytest.fixture
def registry():
    reg = ToolRegistry()

    @reg.register("calculator", CalculatorInput)
    def calc(expression: str) -> str:
        return f"Result: {expression}"

    @reg.register("greet", GreetInput)
    def greet(name: str) -> str:
        return f"Hello, {name}"

    return reg


class TestToolRegistry:
    def test_register_adds_tool(self, registry):
        assert "calculator" in registry.tools
        assert "calculator" in registry.schemas

    def test_call_tool_returns_result(self, registry):
        result = registry.call_tool("calculator", {"expression": "2+2"})
        assert "Result" in result

    def test_call_tool_validates_args(self, registry):
        with pytest.raises(Exception):
            registry.call_tool("greet", {"bad_field": 123})

    def test_call_tool_missing_raises_keyerror(self, registry):
        with pytest.raises(KeyError, match="not found"):
            registry.call_tool("nonexistent", {})

    def test_list_tools_returns_entries(self, registry):
        tools = registry.list_tools()
        assert len(tools) == 2
        assert tools[0]["name"] in ["calculator", "greet"]

    def test_get_schema_returns_dict(self, registry):
        schema = registry.get_schema("calculator")
        assert "properties" in schema
        assert "expression" in schema["properties"]

    def test_get_schema_missing_raises(self, registry):
        with pytest.raises(KeyError, match="not found"):
            registry.get_schema("nope")

    def test_register_duplicate_overwrites(self, registry):
        class NewInput(BaseModel):
            value: str

        @registry.register("calculator", NewInput)
        def new_calc(value: str) -> str:
            return f"New: {value}"

        result = registry.call_tool("calculator", {"value": "test"})
        assert "New" in result
