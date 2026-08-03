from app.main import app
from fastapi.testclient import TestClient


def test_health_endpoint_reports_service_ready() -> None:
    response = TestClient(app).get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
