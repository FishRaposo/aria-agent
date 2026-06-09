from unittest.mock import MagicMock, patch


def test_health_endpoint():
    mock_db = MagicMock()
    mock_redis = MagicMock()
    mock_redis.ping.return_value = True

    with (
        patch("aria_agent.main.db_manager", mock_db),
        patch("aria_agent.main.redis_manager", mock_redis),
        patch("aria_agent.main.registry", MagicMock()),
        patch("aria_agent.main.gate", MagicMock()),
        patch("aria_agent.main.agent", MagicMock()),
    ):
        from fastapi.testclient import TestClient

        from aria_agent.main import app

        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200
            assert response.json()["service"] == "aria-agent"
            assert "dependencies" in response.json()
