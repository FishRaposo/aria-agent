"""Clean-break namespace contract for the ARIA framework identity."""

from __future__ import annotations

import ast
import importlib
import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_NOTE = Path(
    "docs/migrations/2026-08-12-" + "her" + "mes-to-aria-clean-break.md"
)
IGNORED_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
}


def _parsed_source(relative_path: str) -> ast.Module:
    return ast.parse((REPO_ROOT / relative_path).read_text(encoding="utf-8"))


def _string_literals(relative_path: str) -> set[str]:
    return {
        node.value
        for node in ast.walk(_parsed_source(relative_path))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }


def test_aria_source_package_replaces_legacy_namespace():
    assert (REPO_ROOT / "src/aria/__init__.py").is_file()
    assert not (REPO_ROOT / ("src/" + "her" + "mes")).exists()


def test_aria_agent_is_the_declared_public_class():
    class_names = {
        node.name
        for node in ast.walk(_parsed_source("src/aria/agents.py"))
        if isinstance(node, ast.ClassDef)
    }

    assert "AriaAgent" in class_names
    assert "Her" + "mesAgent" not in class_names


def test_aria_service_identity_is_declared_in_config():
    assignments = {
        target.id: node.value.value
        for node in ast.walk(_parsed_source("src/aria/config.py"))
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
        for target in [node.target]
    }

    assert assignments["APP_NAME"] == "aria-agent-framework"


def test_only_aria_environment_settings_are_declared():
    file_reader_literals = _string_literals("src/aria/builtin_tools/file_reader.py")
    web_search_literals = _string_literals("src/aria/builtin_tools/web_search.py")

    assert "ARIA_SANDBOX_DIR" in file_reader_literals
    assert "ARIA_SEARCH_API_URL" in web_search_literals
    assert "HER" + "MES_SANDBOX_DIR" not in file_reader_literals
    assert "HER" + "MES_SEARCH_API_URL" not in web_search_literals


def test_only_aria_celery_task_names_are_declared():
    worker_literals = _string_literals("src/aria/worker.py")

    assert "aria.run_agent" in worker_literals
    assert "aria.sweep_expired_approvals" in worker_literals
    assert "her" + "mes.run_agent" not in worker_literals
    assert "her" + "mes.sweep_expired_approvals" not in worker_literals


def test_aria_package_and_public_agent_are_importable():
    package_spec = importlib.util.find_spec("aria")
    assert package_spec is not None, "the aria package must be the runtime namespace"

    agents = importlib.import_module("aria.agents")
    assert agents.AriaAgent.__name__ == "AriaAgent"


def test_legacy_package_is_not_importable():
    legacy_package = "her" + "mes"
    assert importlib.util.find_spec(legacy_package) is None


def test_service_identity_uses_aria_package_name():
    config_module = importlib.import_module("aria.config")
    assert config_module.AppConfig().APP_NAME == "aria-agent-framework"


def test_aria_sandbox_setting_controls_file_access(tmp_path, monkeypatch):
    file_reader_module = importlib.import_module("aria.builtin_tools.file_reader")
    legacy_setting = "HER" + "MES_SANDBOX_DIR"
    legacy_root = tmp_path / "legacy"
    aria_root = tmp_path / "aria"
    legacy_root.mkdir()
    aria_root.mkdir()
    (legacy_root / "identity.txt").write_text("wrong namespace", encoding="utf-8")
    (aria_root / "identity.txt").write_text("ARIA namespace", encoding="utf-8")

    monkeypatch.setenv(legacy_setting, str(legacy_root))
    monkeypatch.setenv("ARIA_SANDBOX_DIR", str(aria_root))

    assert "ARIA namespace" in file_reader_module.file_reader("identity.txt")


def test_legacy_sandbox_setting_is_not_a_fallback(tmp_path, monkeypatch):
    file_reader_module = importlib.import_module("aria.builtin_tools.file_reader")
    legacy_setting = "HER" + "MES_SANDBOX_DIR"
    legacy_root = tmp_path / "legacy"
    legacy_root.mkdir()
    (legacy_root / "legacy-only.txt").write_text("must not be read", encoding="utf-8")

    monkeypatch.delenv("ARIA_SANDBOX_DIR", raising=False)
    monkeypatch.setenv(legacy_setting, str(legacy_root))

    assert "must not be read" not in file_reader_module.file_reader("legacy-only.txt")


def test_aria_search_setting_selects_configured_endpoint(monkeypatch):
    web_search_module = importlib.import_module("aria.builtin_tools.web_search")
    observed = {}

    async def fake_real_search(query: str, api_url: str) -> str:
        observed.update(query=query, api_url=api_url)
        return "configured search result"

    monkeypatch.setattr(web_search_module, "_real_search", fake_real_search)
    monkeypatch.setenv("ARIA_SEARCH_API_URL", "https://search.example.test")
    monkeypatch.setenv("HER" + "MES_SEARCH_API_URL", "https://legacy.example.test")

    assert web_search_module.web_search("namespace") == "configured search result"
    assert observed == {
        "query": "namespace",
        "api_url": "https://search.example.test",
    }


def test_legacy_search_setting_is_not_a_fallback(monkeypatch):
    web_search_module = importlib.import_module("aria.builtin_tools.web_search")
    monkeypatch.delenv("ARIA_SEARCH_API_URL", raising=False)
    monkeypatch.setenv("HER" + "MES_SEARCH_API_URL", "https://legacy.example.test")

    assert "Python" in web_search_module.web_search("python")


def test_celery_registers_only_aria_task_names():
    worker = importlib.import_module("aria.worker")
    legacy_prefix = "her" + "mes."

    assert "aria.run_agent" in worker.celery_app.tasks
    assert "aria.sweep_expired_approvals" in worker.celery_app.tasks
    assert not any(name.startswith(legacy_prefix) for name in worker.celery_app.tasks)


def test_runtime_facing_files_contain_no_legacy_identity():
    forbidden = ("Her" + "mes", "her" + "mes", "HER" + "MES")
    violations: list[str] = []

    for path in REPO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative_path = path.relative_to(REPO_ROOT)
        if relative_path == MIGRATION_NOTE or any(
            part in IGNORED_PARTS or part.endswith(".egg-info")
            for part in relative_path.parts
        ):
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if any(term in content for term in forbidden):
            violations.append(relative_path.as_posix())

    assert violations == []
