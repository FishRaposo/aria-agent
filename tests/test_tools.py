"""Unit + golden tests for the tool registry and every builtin tool."""

import pytest
from pydantic import BaseModel, ValidationError

from aria.builtin_tools.calculator import calculator, safe_eval
from aria.builtin_tools.email_draft import EmailDraftInput, email_draft
from aria.builtin_tools.file_reader import file_reader, get_sandbox_root
from aria.builtin_tools.task_creator import make_task_creator, task_creator
from aria.builtin_tools.web_search import web_search
from aria.store import InMemoryTaskStore
from aria.tools import Permission, ToolRegistry


# --------------------------------------------------------------------------- #
# Calculator (safe AST evaluator)
# --------------------------------------------------------------------------- #
class TestCalculator:
    @pytest.mark.parametrize(
        "expr,expected",
        [
            ("2 + 2", 4),
            ("120 + 350", 470),
            ("10 - 3 * 2", 4),
            ("(1 + 2) * 3", 9),
            ("2 ** 10", 1024),
            ("7 / 2", 3.5),
            ("7 // 2", 3),
            ("10 % 3", 1),
            ("-5 + 2", -3),
        ],
    )
    def test_golden_results(self, expr, expected):
        assert safe_eval(expr) == expected

    def test_calculator_string_output(self):
        assert calculator("120 + 350") == "Result: 470"

    def test_integral_float_normalised(self):
        assert calculator("4.0 + 0") == "Result: 4"

    def test_division_by_zero_is_handled(self):
        assert "division by zero" in calculator("1 / 0")

    @pytest.mark.parametrize(
        "payload",
        [
            "__import__('os').system('echo hi')",
            "open('x')",
            "x + 1",  # name reference
            "().__class__",  # attribute access
            "[1, 2, 3]",  # non-arithmetic literal
            "lambda: 1",
        ],
    )
    def test_calculator_rejects_unsafe(self, payload):
        # Must never raise to the caller and never execute code.
        out = calculator(payload)
        assert out.startswith("Error")

    def test_safe_eval_raises_on_names(self):
        with pytest.raises(ValueError):
            safe_eval("os")

    def test_huge_exponent_rejected(self):
        assert "Error" in calculator("9 ** 100000")

    def test_complex_result_rejected(self):
        # A fractional power of a negative base yields a Python complex; the
        # tool must surface a clean error rather than leak the complex value.
        out = calculator("(-8) ** 0.5")
        assert out.startswith("Error")
        assert "complex result not supported" in out

    def test_safe_eval_raises_on_complex(self):
        with pytest.raises(ValueError, match="complex result not supported"):
            safe_eval("(-8) ** 0.5")


# --------------------------------------------------------------------------- #
# File reader (sandboxed)
# --------------------------------------------------------------------------- #
class TestFileReader:
    @pytest.fixture
    def sandbox(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ARIA_SANDBOX_DIR", str(tmp_path))
        (tmp_path / "ok.txt").write_text("hello sandbox", encoding="utf-8")
        return tmp_path

    def test_reads_file_inside_sandbox(self, sandbox):
        out = file_reader("ok.txt")
        assert "hello sandbox" in out

    def test_missing_file(self, sandbox):
        assert "not found" in file_reader("nope.txt").lower()

    @pytest.mark.parametrize(
        "payload",
        [
            "../secret.txt",
            "../../etc/passwd",
            "../../../Windows/System32/drivers/etc/hosts",
            "..\\..\\secret.txt",
        ],
    )
    def test_path_traversal_blocked(self, sandbox, payload):
        out = file_reader(payload)
        assert "access denied" in out.lower() or "not found" in out.lower()
        # Critically, never leaks content outside the sandbox.
        assert "root:" not in out

    def test_absolute_path_outside_sandbox_blocked(self, sandbox):
        out = file_reader("C:/Windows/win.ini")
        assert "access denied" in out.lower() or "not found" in out.lower()

    def test_get_sandbox_root_exists(self):
        root = get_sandbox_root()
        assert root.exists() and root.is_dir()


# --------------------------------------------------------------------------- #
# Web search (deterministic mock offline)
# --------------------------------------------------------------------------- #
class TestWebSearch:
    def test_known_keyword(self, monkeypatch):
        monkeypatch.delenv("ARIA_SEARCH_API_URL", raising=False)
        assert "Python" in web_search("tell me about python")

    def test_unknown_keyword_default(self, monkeypatch):
        monkeypatch.delenv("ARIA_SEARCH_API_URL", raising=False)
        assert "No relevant results" in web_search("zxqw unknown topic")

    def test_deterministic(self, monkeypatch):
        monkeypatch.delenv("ARIA_SEARCH_API_URL", raising=False)
        assert web_search("rag systems") == web_search("rag systems")


# --------------------------------------------------------------------------- #
# Task creator (persistence)
# --------------------------------------------------------------------------- #
class TestTaskCreator:
    def test_stateless_default(self):
        assert "Task created" in task_creator("Title", "Body")

    def test_persists_into_store(self):
        store = InMemoryTaskStore()
        creator = make_task_creator(store)
        out = creator("Write report", "Quarterly numbers")
        assert "id=" in out
        assert len(store.list()) == 1
        assert store.list()[0]["title"] == "Write report"


# --------------------------------------------------------------------------- #
# Email draft (structured, never sends)
# --------------------------------------------------------------------------- #
class TestEmailDraft:
    def test_returns_structured_draft(self):
        import json

        out = json.loads(email_draft("a@b.com", "Hi", "Body"))
        assert out["sent"] is False
        assert out["to"] == "a@b.com"
        assert out["status"] == "drafted"

    def test_recipient_validation(self):
        with pytest.raises(ValidationError):
            EmailDraftInput(recipient="not-an-email", subject="s", body="b")


# --------------------------------------------------------------------------- #
# Tool registry + permission levels
# --------------------------------------------------------------------------- #
class TestToolRegistry:
    def test_default_registry_has_five_tools(self, registry):
        assert len(registry.names()) == 5

    def test_permission_levels(self, registry):
        assert registry.permission_for("calculator") == Permission.SAFE
        assert registry.permission_for("web_search") == Permission.SAFE
        assert registry.permission_for("file_reader") == Permission.SAFE
        assert registry.requires_approval("task_creator") is True
        assert registry.requires_approval("email_draft") is True

    def test_call_tool_validates_args(self, registry):
        with pytest.raises(ValidationError):
            registry.call_tool("calculator", {"wrong": "x"})

    def test_call_tool_missing_raises_keyerror(self, registry):
        with pytest.raises(KeyError, match="not found"):
            registry.call_tool("nonexistent", {})

    def test_list_tools_includes_permission(self, registry):
        tools = {t["name"]: t for t in registry.list_tools()}
        assert tools["task_creator"]["permission"] == "requires_approval"
        assert "schema" in tools["calculator"]

    def test_get_schema_missing_raises(self, registry):
        with pytest.raises(KeyError):
            registry.get_schema("nope")

    def test_decorator_registration(self):
        reg = ToolRegistry()

        class Inp(BaseModel):
            x: int

        @reg.register("double", Inp, Permission.SAFE)
        def double(x: int) -> int:
            return x * 2

        assert reg.call_tool("double", {"x": 3}) == 6
        assert reg.permission_for("double") == Permission.SAFE

    def test_persisting_task_creator_wired(self, registry, task_store):
        registry.call_tool("task_creator", {"title": "T", "description": "D"})
        assert len(task_store.list()) == 1
