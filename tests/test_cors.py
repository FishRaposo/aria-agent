"""Opt-in browser access exercises the real API and CORS preflight boundary."""

import importlib

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from aria.config import AppConfig


@pytest.fixture
def cors_client(monkeypatch):
    import aria.config as settings
    import aria.db as database
    import aria.main as gateway

    monkeypatch.setattr(database, "check_db", lambda: False)
    monkeypatch.setattr(database, "db_available", False)

    def create(origins):
        config = AppConfig(
            _env_file=None,
            CORS_ALLOWED_ORIGINS=origins,
            AGENT_MODE="free_running",
            ARIA_SAFETY_MODE="warn",
        )
        monkeypatch.setattr(settings, "AppConfig", lambda: config)
        importlib.reload(gateway)
        return TestClient(gateway.app)

    yield create


def preflight(client, origin, *, method="POST", headers="content-type"):
    return client.options(
        "/agent/chat",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": headers,
        },
    )


def test_cors_default_is_disabled(monkeypatch):
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    assert AppConfig(_env_file=None).CORS_ALLOWED_ORIGINS == ""


def test_explicit_local_origin_preflight_and_actual_api(cors_client):
    with cors_client("http://localhost:3000, https://preview.example.test") as client:
        response = preflight(client, "http://localhost:3000")
        assert response.status_code == 200
        assert (
            response.headers["access-control-allow-origin"] == "http://localhost:3000"
        )
        assert response.headers["access-control-allow-methods"] == "GET, POST"
        assert "access-control-allow-credentials" not in response.headers
        actual = client.post(
            "/agent/chat",
            headers={"Origin": "http://localhost:3000"},
            json={"message": "calculate 1 + 2"},
        )
        assert actual.status_code == 200
        assert "3" in actual.json()["reply"]
        assert actual.headers["access-control-allow-origin"] == "http://localhost:3000"
        assert client.get("/health").status_code == 200
        assert "access-control-allow-origin" not in client.get("/health").headers


def test_unlisted_origin_preflight_is_denied(cors_client):
    with cors_client("http://localhost:3000") as client:
        response = preflight(client, "http://unlisted.example.test")
        assert response.status_code == 400
        assert "access-control-allow-origin" not in response.headers


def test_disabled_cors_does_not_add_origin_headers_or_change_api(cors_client):
    with cors_client("") as client:
        response = preflight(client, "http://localhost:3000")
        assert response.status_code == 405
        assert "access-control-allow-origin" not in response.headers
        assert client.get("/tools").status_code == 200


@pytest.mark.parametrize(
    "method,headers", [("DELETE", "content-type"), ("POST", "authorization")]
)
def test_cors_does_not_authorize_extra_methods_or_headers(cors_client, method, headers):
    with cors_client("http://localhost:3000") as client:
        assert (
            preflight(
                client, "http://localhost:3000", method=method, headers=headers
            ).status_code
            == 400
        )


@pytest.mark.parametrize(
    "origins",
    [
        "*",
        "http://*.example.test",
        "http://localhost:3000/route",
        "http://user:password@localhost:3000",
        "http://localhost:bad",
        "http://localhost:3000?query=1",
        "http://localhost:3000#fragment",
        "javascript:example",
        "http://localhost:3000, *",
    ],
)
def test_cors_rejects_non_origin_configuration(origins):
    with pytest.raises(ValidationError):
        AppConfig(_env_file=None, CORS_ALLOWED_ORIGINS=origins)
