from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

from app.main import create_app
from fastapi.testclient import TestClient
from spend_memory.api.dependencies import (
    get_ingestion_service,
    get_local_workspace_refresh,
)
from spend_memory.local_refresh import LocalRefreshError
from spend_memory.storage.repository import ImportRepositoryError, ImportResult


class _Imports:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def import_document(self, **kwargs: object) -> ImportResult:
        self.calls.append(kwargs)
        if kwargs["document"] == b"large":
            raise ImportRepositoryError("document_too_large")
        return ImportResult(
            UUID(int=1), UUID(int=2), 1, len(self.calls) > 1, "canonical-csv", "1.1"
        )

    def inspect_document(self, document_id: UUID):
        return SimpleNamespace(
            document_id=document_id,
            run_id=UUID(int=2),
            original_filename="statement.csv",
            mime_type="text/csv",
            byte_size=42,
            transaction_count=1,
            parser_id="canonical-csv",
            parser_version="1.1",
            is_demo=False,
        )

    def reprocess_document(self, document_id: UUID) -> ImportResult:
        self.calls.append({"reprocess_document_id": document_id})
        return ImportResult(document_id, UUID(int=3), 1, False, "canonical-csv", "1.2")


class _Refresh:
    def refresh(self) -> None:
        pass


class _BrokenRefresh:
    def refresh(self) -> None:
        raise LocalRefreshError


def _client(tmp_path: Path, service: _Imports) -> TestClient:
    app = create_app(tmp_path / "spend-memory.duckdb", tmp_path / "data")
    app.dependency_overrides[get_ingestion_service] = lambda: service
    app.dependency_overrides[get_local_workspace_refresh] = _Refresh
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
        "parser_id": "canonical-csv",
        "parser_version": "1.1",
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
    app = create_app(tmp_path / "spend-memory.duckdb", tmp_path / "data")
    app.dependency_overrides[get_local_workspace_refresh] = _Refresh
    client = TestClient(app)
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


def test_import_hides_local_refresh_failures(tmp_path: Path) -> None:
    service = _Imports()
    app = create_app(tmp_path / "spend-memory.duckdb", tmp_path / "data")
    app.dependency_overrides[get_ingestion_service] = lambda: service
    app.dependency_overrides[get_local_workspace_refresh] = _BrokenRefresh

    response = TestClient(app).post(
        "/api/v1/imports",
        files={"file": ("statement.csv", b"safe", "text/csv")},
    )

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "local_refresh_failed",
            "message": "The statement was saved, but local activity could not be refreshed.",
            "details": [],
        }
    }


def test_import_requires_a_multipart_file(tmp_path: Path) -> None:
    response = _client(tmp_path, _Imports()).post("/api/v1/imports")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


def test_import_inspection_and_reprocess_expose_only_safe_local_metadata(tmp_path: Path) -> None:
    service = _Imports()
    client = _client(tmp_path, service)
    document_id = "00000000-0000-0000-0000-000000000001"

    inspected = client.get(f"/api/v1/imports/{document_id}")
    reprocessed = client.post(f"/api/v1/imports/{document_id}/reprocess")

    assert inspected.status_code == 200
    assert inspected.json() == {
        "document_id": document_id,
        "run_id": "00000000-0000-0000-0000-000000000002",
        "original_filename": "statement.csv",
        "mime_type": "text/csv",
        "byte_size": 42,
        "transaction_count": 1,
        "parser_id": "canonical-csv",
        "parser_version": "1.1",
        "is_demo": False,
    }
    assert reprocessed.status_code == 201
    assert reprocessed.json()["run_id"] == "00000000-0000-0000-0000-000000000003"
    assert service.calls[-1] == {"reprocess_document_id": UUID(document_id)}
