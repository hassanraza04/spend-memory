from datetime import date
from pathlib import Path
from uuid import UUID

from app.main import create_app
from fastapi.testclient import TestClient
from spend_memory.api.dependencies import get_enrichment_repository
from spend_memory.enrichment.models import CategoryDecision, TrustedTransaction
from spend_memory.enrichment.search import SearchRow

from apps.api.tests.test_analytics_models import _build_fixture_database, _dbt_build


def _row(identifier: int, amount_minor: int = 1200, direction: str = "debit") -> SearchRow:
    return SearchRow(
        TrustedTransaction(UUID(int=identifier), "AED-001", date(2026, 1, identifier), "Rina lunch", "rina lunch", "AED", amount_minor, direction),
        CategoryDecision(None, "uncategorized", "unavailable"),
        None,
        "unresolved",
        source_document="statement.csv",
        source_ordinal=identifier,
        source_page=None,
        source_row=identifier + 1,
        source_text="2026-01-01,Rina lunch,-12.00",
        extraction_confidence=0.95,
    )


class _Rows:
    def list_search_rows(self) -> list[SearchRow]:
        return [_row(1), _row(2, 300, "credit")]


def _client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "spend-memory.duckdb", tmp_path / "data")
    app.dependency_overrides[get_enrichment_repository] = _Rows
    return TestClient(app)


def test_transactions_page_trusted_rows_and_source_evidence(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/api/v1/transactions?limit=1&offset=1")

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "transaction_id": "00000000-0000-0000-0000-000000000001",
                "transaction_date": "2026-01-01",
                "account": "AED-001",
                "description": "Rina lunch",
                "currency": "AED",
                "amount_minor": 1200,
                "direction": "debit",
                "merchant": None,
                "category": "uncategorized",
                "counterparty": None,
                "state": "unresolved",
                "source": {
                    "document": "statement.csv",
                    "ordinal": 1,
                    "page": None,
                    "row": 2,
                    "text": "2026-01-01,Rina lunch,-12.00",
                    "extraction_confidence": 0.95,
                },
            }
        ],
        "limit": 1,
        "offset": 1,
        "total": 2,
    }


def test_transactions_reject_invalid_direction(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/api/v1/transactions?direction=outbound")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


def test_transactions_read_trusted_mart_rows_only(tmp_path: Path) -> None:
    database_path = _build_fixture_database(tmp_path)
    _dbt_build(database_path, "mart_transactions")

    response = TestClient(
        create_app(database_path, tmp_path / "documents")
    ).get("/api/v1/transactions?limit=1")

    assert response.status_code == 200
    assert response.json()["total"] == 864
    document = response.json()["items"][0]["source"]["document"]
    assert document.endswith((".csv", ".pdf"))
