"""Tests for external integration surfaces (Hermes/CMD/OpenCode bridges)."""
import os
import sys

from fastapi.testclient import TestClient


ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "..", "operator-shared-core", "src"))


def test_openai_compatible_models_exposes_virtual_aria_routes():
    from aria_agent.main import app

    client = TestClient(app)
    resp = client.get("/v1/models")
    assert resp.status_code == 200
    data = resp.json()["data"]
    ids = {m["id"] for m in data}
    assert "aria/auto" in ids
    assert "aria/route" in ids
    assert "aria/role/implementer" in ids


def test_openai_compatible_route_model_returns_route_json_text():
    from aria_agent.main import app

    client = TestClient(app)
    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "aria/route",
            "messages": [{"role": "user", "content": "Review this code for bugs"}],
        },
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["object"] == "chat.completion"
    content = payload["choices"][0]["message"]["content"]
    assert '"task_type": "code_review"' in content
    assert '"primary"' in content


def test_openai_compatible_streaming_route_emits_sse_done():
    from aria_agent.main import app

    client = TestClient(app)
    with client.stream(
        "POST",
        "/v1/chat/completions",
        json={
            "model": "aria/route",
            "stream": True,
            "messages": [{"role": "user", "content": "Review this code for bugs"}],
        },
    ) as resp:
        assert resp.status_code == 200
        text = "".join(resp.iter_text())
    assert "chat.completion.chunk" in text
    assert "data: [DONE]" in text


def test_aria_cmd_model_mapping_prefers_budget_over_route():
    from integrations.aria_cmd import command_code_model

    route = {"primary": {"model_id": "MiniMax-M3"}}
    assert command_code_model(route, budget="cheap") == "xiaomi/mimo-v2.5"
    assert command_code_model(route) == "MiniMaxAI/MiniMax-M3"
