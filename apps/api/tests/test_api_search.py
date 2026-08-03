from datetime import date
from pathlib import Path
from uuid import UUID

from app.main import create_app
from fastapi.testclient import TestClient
from spend_memory.api.dependencies import get_enrichment_repository
from spend_memory.enrichment.models import CategoryDecision, TrustedTransaction
from spend_memory.enrichment.search import SearchRow


def _row(identifier: int, direction: str, amount_minor: int) -> SearchRow:
    return SearchRow(
        TrustedTransaction(UUID(int=identifier), "AED-001", date(2026, 1, identifier), "Rina transfer", "rina transfer", "AED", amount_minor, direction),
        CategoryDecision(None, "uncategorized", "unavailable"),
        None,
        "unresolved",
        source_document="statement.csv",
        source_ordinal=identifier,
        source_page=None,
        source_row=identifier + 1,
        source_text="evidence",
        extraction_confidence=1.0,
        counterparty_label="Rina",
    )


class _Rows:
    def list_search_rows(self) -> list[SearchRow]:
        return [_row(1, "debit", 1200), _row(2, "credit", 200)]


def test_search_returns_structured_account_scope_and_pre_paging_aed_lens(tmp_path: Path) -> None:
    app = create_app(tmp_path / "spend-memory.duckdb", tmp_path / "data")
    app.dependency_overrides[get_enrichment_repository] = _Rows

    response = TestClient(app).get("/api/v1/search?query=Rina&account=AED-001&limit=1")

    assert response.status_code == 200
    assert response.json()["query"] == "Rina"
    assert len(response.json()["items"]) == 1
    assert response.json()["lens"] == [
        {
            "currency": "AED",
            "sent_minor": 1200,
            "received_minor": 200,
            "net_minor": -1000,
            "transaction_count": 2,
        }
    ]
