from unittest.mock import MagicMock, patch


def test_health_endpoint():
    mock_db = MagicMock()
    mock_redis = MagicMock()
    mock_redis.ping.return_value = True

    with (
        patch("hermes.main.db_manager", mock_db),
        patch("hermes.main.redis_manager", mock_redis),
        patch("hermes.main.registry", MagicMock()),
        patch("hermes.main.gate", MagicMock()),
        patch("hermes.main.agent", MagicMock()),
    ):
        from fastapi.testclient import TestClient

        from hermes.main import app

        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200
            assert response.json()["service"] == "aria-agent"
            assert "dependencies" in response.json()
