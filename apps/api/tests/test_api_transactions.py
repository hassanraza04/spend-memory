from datetime import date
from pathlib import Path
from uuid import UUID

import duckdb
from app.main import create_app
from fastapi.testclient import TestClient
from spend_memory.api.dependencies import get_enrichment_repository
from spend_memory.enrichment.models import CategoryDecision, TrustedTransaction
from spend_memory.enrichment.repository import EnrichmentRepository
from spend_memory.enrichment.search import SearchRow
from spend_memory.enrichment.service import EnrichmentService

from apps.api.tests.test_analytics_models import _build_fixture_database, _dbt_build


def _row(
    identifier: int,
    transaction_date: date,
    amount_minor: int = 1200,
    direction: str = "debit",
) -> SearchRow:
    return SearchRow(
        TrustedTransaction(UUID(int=identifier), "AED-001", transaction_date, "Rina lunch", "rina lunch", "AED", amount_minor, direction),
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
        return [
            _row(1, date(2026, 1, 1)),
            _row(2, date(2026, 2, 1), 300, "credit"),
        ]


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


def test_transactions_and_lens_use_an_inclusive_start_and_exclusive_end_date(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)

    transactions = client.get("/api/v1/transactions?after=2026-01-01&before=2026-02-01")
    lens = client.get("/api/v1/lens?after=2026-01-01&before=2026-02-01")

    assert transactions.status_code == lens.status_code == 200
    assert [item["transaction_id"] for item in transactions.json()["items"]] == [
        "00000000-0000-0000-0000-000000000001"
    ]
    assert transactions.json()["total"] == 1
    assert lens.json()["lens"] == [
        {
            "currency": "AED",
            "sent_minor": 1200,
            "received_minor": 0,
            "net_minor": -1200,
            "transaction_count": 1,
        }
    ]


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


def test_empty_workspace_reports_trusted_records_are_not_ready(tmp_path: Path) -> None:
    response = TestClient(
        create_app(tmp_path / "spend-memory.duckdb", tmp_path / "documents")
    ).get("/api/v1/transactions")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "trusted_records_unavailable"


def test_transactions_use_the_local_database_connection_mode(tmp_path: Path) -> None:
    database_path = _build_fixture_database(tmp_path)
    _dbt_build(database_path, "mart_transactions")

    with duckdb.connect(str(database_path)):
        response = TestClient(
            create_app(database_path, tmp_path / "documents")
        ).get("/api/v1/transactions?limit=1")

    assert response.status_code == 200


def test_review_evidence_uses_the_local_database_connection_mode(tmp_path: Path) -> None:
    database_path = _build_fixture_database(tmp_path)
    _dbt_build(database_path, "mart_transactions")
    EnrichmentService(EnrichmentRepository(database_path)).refresh()
    _dbt_build(database_path, "mart_recurring_groups mart_transactions")

    with duckdb.connect(str(database_path)):
        client = TestClient(create_app(database_path, tmp_path / "documents"))
        merchants = client.get("/api/v1/merchants")
        categories = client.get("/api/v1/categories")
        recurring = client.get("/api/v1/recurring")
        review = client.get("/api/v1/review")

    assert merchants.status_code == categories.status_code == recurring.status_code == review.status_code == 200
