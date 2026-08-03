from pathlib import Path
from uuid import UUID

from app.main import create_app
from fastapi.testclient import TestClient
from spend_memory.api.dependencies import get_ingestion_service
from spend_memory.storage.repository import ImportRepositoryError, ImportResult


class _Imports:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def import_document(self, **kwargs: object) -> ImportResult:
        self.calls.append(kwargs)
        if kwargs["document"] == b"large":
            raise ImportRepositoryError("document_too_large")
        return ImportResult(UUID(int=1), UUID(int=2), 1, len(self.calls) > 1)


def _client(tmp_path: Path, service: _Imports) -> TestClient:
    app = create_app(tmp_path / "spend-memory.duckdb", tmp_path / "data")
    app.dependency_overrides[get_ingestion_service] = lambda: service
    return TestClient(app)


def test_imports_only_forward_upload_bytes_filename_and_mime_type(tmp_path: Path) -> None:
    service = _Imports()
    response = _client(tmp_path, service).post(
        "/api/v1/imports",
        files={"file": ("statement.csv", b"date,description,amount\n", "text/csv")},
    )

    assert response.status_code == 201
    assert response.json() == {
        "document_id": "00000000-0000-0000-0000-000000000001",
        "run_id": "00000000-0000-0000-0000-000000000002",
        "transaction_count": 1,
        "was_already_imported": False,
    }
    assert service.calls == [
        {
            "document": b"date,description,amount\n",
            "filename": "statement.csv",
            "declared_mime_type": "text/csv",
        }
    ]


def test_import_retry_exposes_existing_result_without_details(tmp_path: Path) -> None:
    service = _Imports()
    client = _client(tmp_path, service)
    files = {"file": ("statement.csv", b"same", "text/csv")}

    client.post("/api/v1/imports", files=files)
    response = client.post("/api/v1/imports", files=files)

    assert response.status_code == 201
    assert response.json()["was_already_imported"] is True


def test_safe_csv_import_and_duplicate_retry_use_the_local_ingress(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "spend-memory.duckdb", tmp_path / "data"))
    document = (
        b"transaction_id,posted_date,account_id,currency,amount_minor,description,transaction_type\n"
        b"SYN-00001,2026-01-01,AED-SYNTH-001,AED,-1200,Synthetic lunch,debit\n"
    )
    files = {"file": ("statement.csv", document, "text/csv")}

    first = client.post("/api/v1/imports", files=files)
    retry = client.post("/api/v1/imports", files=files)

    assert first.status_code == retry.status_code == 201
    assert first.json()["was_already_imported"] is False
    assert retry.json()["was_already_imported"] is True
    assert retry.json()["document_id"] == first.json()["document_id"]


def test_import_rejects_oversized_document_with_safe_error(tmp_path: Path) -> None:
    response = _client(tmp_path, _Imports()).post(
        "/api/v1/imports",
        files={"file": ("statement.csv", b"large", "text/csv")},
    )

    assert response.status_code == 413
    assert response.json() == {
        "error": {
            "code": "document_too_large",
            "message": "The document is too large.",
            "details": [],
        }
    }


def test_import_requires_a_multipart_file(tmp_path: Path) -> None:
    response = _client(tmp_path, _Imports()).post("/api/v1/imports")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"
