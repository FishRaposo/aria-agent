"""API contracts for streaming, replay, and local memory search."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from aria.main import app

    with TestClient(app) as test_client:
        yield test_client


def test_chat_stream_emits_ordered_sse_events(client):
    response = client.post(
        "/agent/chat/stream",
        json={"message": "calculate 2 + 3"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: reasoning" in response.text
    assert "event: complete" in response.text


def test_replay_endpoint_defaults_to_dry_run(client):
    run = client.post("/agent/chat", json={"message": "calculate 4 + 5"}).json()

    response = client.post(f"/agent/runs/{run['run_id']}/replay", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["dry_run"] is True
    assert body["side_effects_executed"] is False
    assert body["run_id"] == run["run_id"]


def test_memory_search_returns_recent_offline_context(client):
    client.post("/agent/chat", json={"message": "calculate 7 + 8"})

    response = client.get(
        "/agent/memory/search",
        params={"query": "calculate", "session_id": "default"},
    )

    assert response.status_code == 200
    assert response.json()["matches"]
