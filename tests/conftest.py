"""Shared test fixtures — all offline (no network, no DB, no keys)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from aria.approvals import ApprovalGate  # noqa: E402
from aria.internal.vendor_core.testing import (  # noqa: E402
    MockDatabase,
    MockRedisClient,
)
from aria.llm_client import AgentLLMClient  # noqa: E402
from aria.memory import AgentMemory  # noqa: E402
from aria.routing import build_router  # noqa: E402
from aria.store import (  # noqa: E402
    InMemoryApprovalStore,
    InMemoryRunStore,
    InMemoryTaskStore,
)
from aria.tools import build_default_registry  # noqa: E402


@pytest.fixture
def mock_db():
    return MockDatabase()


@pytest.fixture
def mock_redis():
    return MockRedisClient()


@pytest.fixture
def task_store():
    return InMemoryTaskStore()


@pytest.fixture
def approval_store():
    return InMemoryApprovalStore()


@pytest.fixture
def run_store():
    return InMemoryRunStore()


@pytest.fixture
def registry(task_store):
    return build_default_registry(task_store=task_store)


@pytest.fixture
def keyword_agent(registry):
    from aria.agents import AriaAgent

    return AriaAgent(
        registry,
        ApprovalGate(enabled=True, mode="free_running"),
        router=build_router("keyword"),
        memory=AgentMemory(),
        mode="free_running",
    )


@pytest.fixture
def sim_llm_agent(registry):
    from aria.agents import AriaAgent

    return AriaAgent(
        registry,
        ApprovalGate(enabled=True, mode="free_running"),
        router=build_router("auto", llm_client=AgentLLMClient()),
        memory=AgentMemory(),
        mode="free_running",
    )
