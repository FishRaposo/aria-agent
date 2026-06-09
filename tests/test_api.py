from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    mock_db = MagicMock()
    mock_redis = MagicMock()
    mock_redis.ping.return_value = True
    with (
        patch("shared_core.database.DatabaseManager.__init__", return_value=None),
        patch("shared_core.redis.RedisManager.__init__", return_value=None),
        patch("shared_core.logging.setup_logging"),
    ):
        from hermes.main import app
        app.dependency_overrides = {}
        return TestClient(app)


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "service" in data or "status" in data


def test_agent_chat_endpoint(client):
    response = client.post("/agent/chat", json={"message": "calculate 2 + 2"})
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert "trace" in data
    assert "cost" in data


def test_tools_list_endpoint(client):
    response = client.get("/tools")
    assert response.status_code == 200
    data = response.json()
    assert "tools" in data
    assert len(data["tools"]) >= 5


def test_tool_schema_endpoint(client):
    response = client.get("/tools/calculator")
    assert response.status_code == 200
    data = response.json()
    assert "properties" in data
