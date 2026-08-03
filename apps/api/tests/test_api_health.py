from pathlib import Path

from app.main import create_app
from fastapi.testclient import TestClient


def test_versioned_health_endpoint_reports_service_ready(tmp_path: Path) -> None:
    response = TestClient(
        create_app(tmp_path / "spend-memory.duckdb", tmp_path / "data")
    ).get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
