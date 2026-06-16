"""Shared test fixtures — all offline (no network, no DB, no keys)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from shared_core.testing import MockDatabase, MockRedisClient  # noqa: E402

from hermes.approvals import ApprovalGate  # noqa: E402
from hermes.llm_client import AgentLLMClient  # noqa: E402
from hermes.memory import AgentMemory  # noqa: E402
from hermes.routing import build_router  # noqa: E402
from hermes.store import (  # noqa: E402
    InMemoryApprovalStore,
    InMemoryRunStore,
    InMemoryTaskStore,
)
from hermes.tools import build_default_registry  # noqa: E402


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
    from hermes.agents import HermesAgent

    return HermesAgent(
        registry,
        ApprovalGate(enabled=True, mode="free_running"),
        router=build_router("keyword"),
        memory=AgentMemory(),
        mode="free_running",
    )


@pytest.fixture
def sim_llm_agent(registry):
    from hermes.agents import HermesAgent

    return HermesAgent(
        registry,
        ApprovalGate(enabled=True, mode="free_running"),
        router=build_router("auto", llm_client=AgentLLMClient()),
        memory=AgentMemory(),
        mode="free_running",
    )
