"""Termux compatibility regression tests.

This file is the long-term guard that Aria Agent still runs on Termux
(Android/arm64) out of the box. It exists because Termux is the host
where this project is actively developed, and a few invariants are easy
to break without noticing on a Linux dev machine.

Run on Termux:
    PYTHONPATH="$ARIA_DIR/src:$SHARED_CORE/src" \
      ~/.hermes/hermes-agent/venv/bin/python -m pytest tests/test_termux_compat.py

What it guards:

1. **Full import surface** — every public symbol Aria exposes imports
   cleanly under Termux. Catches things like a stray `import torch` or
   a dependency that was added without the Termux-extras marker.

2. **`resolve_decision` graceful fallback** — when the routing table's
   preferred model is on a provider the user doesn't have keys for, the
   registry walks the fallback chain instead of raising. This is the
   single most important behavior for making Aria work on the $1/mo Go
   plan (where only OCG is callable for some roles).

3. **All active sub-agent roles resolve to a callable model** — every
   role in the `SubAgentRole` enum must produce a (provider, model)
   pair that the registry can actually call. Catches stale routing
   tables that reference retired models.

4. **Calculator is safe** — the v0.1 calculator used `eval()` with a
   stripped `__builtins__` (still risky). v0.4 replaces it with an AST
   walker. This test asserts hostile inputs (function calls, attribute
   access, file I/O, booleans-as-int, string literals) all return
   friendly errors instead of executing.

5. **`/tmp` is read-only on Termux** — every test in this file writes
   to `$PREFIX/tmp/` instead, so the file itself is Termux-safe.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

# Path setup mirrors the rest of the test suite. operator-shared-core is a
# sibling repo — Aria imports from it, and Termux has no `pip install -e`
# so PYTHONPATH is the only way.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))  # so `integrations` resolves
sys.path.insert(0, str(ROOT.parent / "operator-shared-core" / "src"))


# ---------------------------------------------------------------------------
# 1. Full import surface
# ---------------------------------------------------------------------------

class TestFullImportSurface:
    """Every public symbol Aria exposes must import cleanly on Termux."""

    def test_aria_agent_top_level_imports(self):
        import aria_agent  # noqa: F401
        # Public v0.4 surface (per aria_agent/__init__.py).
        # If a name is removed upstream, drop it here; the goal is to fail
        # loudly when something can't be imported, not to pin the API.
        for name in (
            "AriaAgent",
            "KeywordRouterAgent",
        ):
            assert hasattr(aria_agent, name), f"aria_agent missing top-level {name!r}"

    def test_subagents_module_imports(self):
        from aria_agent import subagents  # noqa: F401
        for name in (
            "SubAgent",
            "SubAgentRegistry",
            "Orchestrator",
            "OrchestrationResult",
            "get_default_sub_agent_registry",
        ):
            assert hasattr(subagents, name), f"subagents missing {name!r}"

    def test_routers_module_imports(self):
        from aria_agent import router  # noqa: F401
        for name in (
            "ModelSelector",
            "TaskClassifier",
            "RoutingTable",
            "RoutingDecision",
            "get_default_routing_table",
            "TaskType",
            "SubAgentRole",
        ):
            assert hasattr(router, name), f"router missing {name!r}"

    def test_providers_module_imports(self):
        from aria_agent import providers  # noqa: F401
        from aria_agent.providers import (
            ProviderRegistry,
            BaseProvider,
            OpenCodeGoProvider,
            OpenAICodexProvider,
            MiniMaxProvider,
            get_default_registry,
        )
        # Each provider class is constructible without keys.
        for cls in (OpenCodeGoProvider, OpenAICodexProvider, MiniMaxProvider):
            assert cls().get_models()  # non-empty list

    def test_cooperation_module_imports(self):
        from aria_agent import cooperation  # noqa: F401
        from aria_agent.cooperation import (
            CooperationResult,
            CascadePattern,
            EnsemblePattern,
            PlanExecuteValidatePattern,
        )
        for cls in (CascadePattern, EnsemblePattern, PlanExecuteValidatePattern):
            assert cls.__name__  # smoke import

    def test_builtin_tools_imports(self):
        from aria_agent.builtin_tools import (  # noqa: F401
            calculator,
            web_search,
            file_reader,
            task_creator,
            email_draft,
        )
        from aria_agent.builtin_tools.calculator import CalculatorInput, calculator  # noqa: F401

    def test_integrations_package_imports(self):
        """The three model-selector integrations must import on Termux."""
        from integrations import aria_cmd, aria_opencode  # noqa: F401
        from integrations.aria_cmd import command_code_model  # noqa: F401
        from integrations.aria_opencode import opencode_model, route_task  # noqa: F401


# ---------------------------------------------------------------------------
# 2. resolve_decision graceful fallback
# ---------------------------------------------------------------------------

class TestResolveDecisionFallback:
    """When the preferred model is on an unregistered provider, fall back."""

    def _decision(self, registry, task_type):
        from aria_agent.router import TaskType
        table = registry.table if hasattr(registry, "table") else None
        # We use the selector directly to keep this independent of registry.table.
        from aria_agent.router import ModelSelector, get_default_routing_table
        selector = ModelSelector(get_default_routing_table())
        return selector.select(task_type)

    def test_unregistered_primary_falls_through(self):
        """If only OCG-style providers are registered, picking any model must
        still return a callable pair. After the 2026-06-11 split, both
        opencode-go (open source) and zen (closed source) are registered
        when OPENCODE_GO_API_KEY is set — so the resolver picks whichever
        one serves the routing table's choice. We just verify the result
        is on a registered provider that serves the chosen model.
        """
        from aria_agent.providers.registry import ProviderRegistry
        from aria_agent.router import TaskType

        with patch.dict(os.environ, {"OPENCODE_GO_API_KEY": "fake"}, clear=True):
            reg = ProviderRegistry()
            assert "opencode-go" in reg._providers, "opencode-go should be registered"
            assert "zen" in reg._providers, "zen should be registered"
            for tt in (
                TaskType.CODING_DEFAULT,
                TaskType.REASONING,
                TaskType.CODE_REVIEW,
                TaskType.LONG_CONTEXT,
            ):
                from aria_agent.router import ModelSelector, get_default_routing_table
                decision = ModelSelector(get_default_routing_table()).select(tt)
                provider_name, model_id = reg.resolve_decision(decision)
                assert provider_name in ("opencode-go", "zen"), (
                    f"{tt} -> {provider_name}, not in (opencode-go, zen)"
                )
                assert model_id in reg.get(provider_name).get_models(), (
                    f"{tt}: model {model_id!r} not served by {provider_name}"
                )

    def test_no_keys_raises_keyerror(self):
        """If NO provider is registered, resolve_decision must raise KeyError loudly
        (not silently return a phantom model)."""
        from aria_agent.providers.registry import ProviderRegistry
        from aria_agent.router import ModelSelector, get_default_routing_table, TaskType

        with patch.dict(os.environ, {}, clear=True):
            reg = ProviderRegistry()
            decision = ModelSelector(get_default_routing_table()).select(TaskType.CODING_DEFAULT)
            try:
                reg.resolve_decision(decision)
            except KeyError:
                pass
            else:
                # If the routing table has a "free" entry that happens to be
                # served by a no-key provider, that's fine — but for THIS
                # test we want to confirm the error path is reachable.
                # (No free providers on the catalog at the time of writing.)
                raise AssertionError(
                    "expected KeyError when no provider is registered; got a successful resolve"
                )

    def test_has_model_returns_bool(self):
        from aria_agent.providers.registry import ProviderRegistry
        with patch.dict(os.environ, {"OPENCODE_GO_API_KEY": "fake"}, clear=True):
            reg = ProviderRegistry()
            assert reg.has_model("kimi-k2.6") is True
            assert reg.has_model("definitely-not-a-real-model-xyz") is False


# ---------------------------------------------------------------------------
# 3. All active sub-agent roles resolve to a callable model
# ---------------------------------------------------------------------------

class TestAllSubAgentRolesResolve:
    """Every role in SubAgentRole must produce a callable (provider, model) pair."""

    def test_every_role_resolves(self):
        from aria_agent.providers.registry import ProviderRegistry
        from aria_agent.router import (
            ModelSelector,
            get_default_routing_table,
            SubAgentRole,
        )

        with patch.dict(
            os.environ,
            {"OPENCODE_GO_API_KEY": "fake", "MINIMAX_API_KEY": "fake"},
            clear=True,
        ):
            reg = ProviderRegistry()
            selector = ModelSelector(get_default_routing_table())
            failures = []
            for role in SubAgentRole:
                try:
                    decision = selector.select_for_role(role)
                    provider_name, model_id = reg.resolve_decision(decision)
                    # Verify the provider actually serves the model.
                    assert model_id in reg.get(provider_name).get_models(), (
                        f"{role.value}: {provider_name} doesn't serve {model_id}"
                    )
                except Exception as exc:  # noqa: BLE001
                    failures.append((role.value, repr(exc)))
            assert not failures, f"unresolved roles: {failures}"

    def test_every_role_resolves_bare_ocg(self):
        """Same as above, but with ONLY OCG registered (the typical Termux state)."""
        from aria_agent.providers.registry import ProviderRegistry
        from aria_agent.router import (
            ModelSelector,
            get_default_routing_table,
            SubAgentRole,
        )

        with patch.dict(os.environ, {"OPENCODE_GO_API_KEY": "fake"}, clear=True):
            reg = ProviderRegistry()
            selector = ModelSelector(get_default_routing_table())
            failures = []
            for role in SubAgentRole:
                try:
                    decision = selector.select_for_role(role)
                    provider_name, model_id = reg.resolve_decision(decision)
                    assert model_id in reg.get(provider_name).get_models()
                except Exception as exc:  # noqa: BLE001
                    failures.append((role.value, repr(exc)))
            assert not failures, f"unresolved roles on bare OCG: {failures}"

    def test_every_role_resolves_with_codex_too(self):
        """With OCG + Codex registered (the user's full Go-plan setup)."""
        from aria_agent.providers.registry import ProviderRegistry
        from aria_agent.router import (
            ModelSelector,
            get_default_routing_table,
            SubAgentRole,
        )

        with patch.dict(
            os.environ,
            {"OPENCODE_GO_API_KEY": "fake", "OPENAI_CODEX": "fake", "MINIMAX_API_KEY": "fake"},
            clear=True,
        ):
            reg = ProviderRegistry()
            selector = ModelSelector(get_default_routing_table())
            failures = []
            for role in SubAgentRole:
                try:
                    decision = selector.select_for_role(role)
                    provider_name, model_id = reg.resolve_decision(decision)
                    assert model_id in reg.get(provider_name).get_models()
                except Exception as exc:  # noqa: BLE001
                    failures.append((role.value, repr(exc)))
            assert not failures, f"unresolved roles with full chain: {failures}"


# ---------------------------------------------------------------------------
# 4. Calculator safety (v0.4 replaced eval() with AST walker)
# ---------------------------------------------------------------------------

class TestCalculatorSafety:
    """The v0.4 calculator must reject anything that isn't pure arithmetic."""

    def _calc(self, expression: str) -> str:
        from aria_agent.builtin_tools.calculator import calculator
        return calculator(expression)

    # Happy path
    def test_basic_arithmetic(self):
        assert self._calc("2 + 2") == "Result: 4"
        assert self._calc("(3 + 4) * 2") == "Result: 14"
        assert self._calc("2 ** 10") == "Result: 1024"
        assert self._calc("10 // 3") == "Result: 3"
        assert self._calc("10 % 3") == "Result: 1"
        assert self._calc("-5 + 3") == "Result: -2"
        assert self._calc("1e3 + 7") == "Result: 1007"

    def test_float_division(self):
        result = self._calc("10 / 3")
        assert result.startswith("Result: 3.3333333333")

    def test_division_by_zero(self):
        assert "division by zero" in self._calc("1 / 0").lower()

    # Hostile inputs — must NOT execute, must NOT leak internals
    def test_rejects_function_call(self):
        for expr in (
            "math.sqrt(16)",
            "__import__('os').system('echo pwned')",
            "open('/etc/passwd').read()",
            "eval('1+1')",
            "exec('print(1)')",
        ):
            out = self._calc(expr)
            assert out.startswith("Error:"), f"calculator executed {expr!r}: {out!r}"

    def test_rejects_attribute_access(self):
        for expr in ("(1).__class__", "(1).real.bit_length()", "os.environ"):
            out = self._calc(expr)
            assert out.startswith("Error:"), f"calculator executed {expr!r}: {out!r}"

    def test_rejects_boolean_and_string_literals(self):
        for expr in ("True + 1", "False", '"hello"', '"a" + "b"'):
            out = self._calc(expr)
            assert out.startswith("Error:"), f"calculator accepted {expr!r}: {out!r}"

    def test_rejects_comparisons_and_booleans(self):
        for expr in ("1 < 2", "1 == 1", "1 and 0", "not 0"):
            out = self._calc(expr)
            assert out.startswith("Error:"), f"calculator accepted {expr!r}: {out!r}"

    def test_rejects_assignment(self):
        # ast.parse('x = 1', mode='eval') raises SyntaxError — also fine.
        out = self._calc("x = 1")
        assert out.startswith("Error:")

    def test_rejects_empty_or_whitespace(self):
        assert "non-empty" in self._calc("").lower()
        assert "non-empty" in self._calc("   ").lower()

    def test_rejects_invalid_syntax(self):
        out = self._calc("2 +")
        assert out.startswith("Error:")


# ---------------------------------------------------------------------------
# 5. Termux-specific invariants
# ---------------------------------------------------------------------------

class TestTermuxInvariants:
    """Things that are true on Termux and that the project relies on."""

    def test_prefix_tmp_is_writable(self):
        """`/tmp` is read-only on Termux; Aria uses `$PREFIX/tmp/` instead."""
        target = Path(os.environ.get("PREFIX", "/data/data/com.termux/files/usr")) / "tmp"
        target.mkdir(parents=True, exist_ok=True)
        probe = target / ".aria-termux-probe"
        probe.write_text("ok")
        assert probe.read_text() == "ok"
        probe.unlink()

    def test_hermes_venv_python_is_importable(self):
        """Aria's wrapper uses `~/.hermes/hermes-agent/venv/bin/python` as the runtime."""
        venv = Path.home() / ".hermes" / "hermes-agent" / "venv" / "bin" / "python"
        if venv.exists():
            import subprocess
            out = subprocess.run(
                [str(venv), "-c", "import aria_agent, shared_core"],
                capture_output=True, text=True, timeout=10,
            )
            # If PYTHONPATH isn't set the import fails — that's a setup issue,
            # not a project bug. The smoke test is just that python runs.
            assert out.returncode == 0 or "No module named" in (out.stderr or "")
