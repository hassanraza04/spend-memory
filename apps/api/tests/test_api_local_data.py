from pathlib import Path

from app.main import create_app
from fastapi.testclient import TestClient
from spend_memory.api.dependencies import get_local_data_service


class _LocalData:
    def __init__(self, real_import: bool = False) -> None:
        self.real_import = real_import
        self.deleted = False
        self.reset = False

    def reset_demo(self) -> None:
        if self.real_import:
            raise ValueError("non_demo_imports_present")
        self.reset = True

    def delete(self) -> None:
        self.deleted = True


def _client(tmp_path: Path, service: _LocalData) -> TestClient:
    app = create_app(tmp_path / "spend-memory.duckdb", tmp_path / "data")
    app.dependency_overrides[get_local_data_service] = lambda: service
    return TestClient(app)


def test_demo_reset_rejects_workspace_with_a_real_import(tmp_path: Path) -> None:
    response = _client(tmp_path, _LocalData(real_import=True)).post("/api/v1/demo/reset")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "non_demo_imports_present"


def test_local_data_deletion_requires_the_exact_confirmation(tmp_path: Path) -> None:
    service = _LocalData()
    client = _client(tmp_path, service)

    rejected = client.request("DELETE", "/api/v1/local-data", json={"confirmation": "delete local data"})
    accepted = client.request("DELETE", "/api/v1/local-data", json={"confirmation": "DELETE LOCAL DATA"})

    assert rejected.status_code == 422
    assert accepted.status_code == 200
    assert accepted.json() == {"status": "deleted"}
    assert service.deleted is True
