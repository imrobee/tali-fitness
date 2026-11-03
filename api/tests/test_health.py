from conftest import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health_returns_ok_without_api_key():
    # /health is the only endpoint that needs no X-API-Key (ARCHITECTURE.md section 11).
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_routes_live_under_api_v1():
    response = client.get("/health")

    assert response.status_code == 404
