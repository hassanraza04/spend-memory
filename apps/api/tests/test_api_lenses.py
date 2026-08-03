from datetime import date
from pathlib import Path
from uuid import UUID

from app.main import create_app
from fastapi.testclient import TestClient
from spend_memory.api.dependencies import get_enrichment_repository
from spend_memory.enrichment.models import CategoryDecision, TrustedTransaction
from spend_memory.enrichment.search import SearchRow


def _row(
    identifier: int,
    transaction_date: date,
    currency: str,
    amount_minor: int,
    direction: str,
) -> SearchRow:
    return SearchRow(
        TrustedTransaction(
            UUID(int=identifier),
            "synthetic",
            transaction_date,
            f"Synthetic {identifier}",
            f"synthetic {identifier}",
            currency,
            amount_minor,
            direction,
        ),
        CategoryDecision(None, "uncategorized", "unavailable"),
        None,
        "unresolved",
    )


class _Rows:
    def list_search_rows(self) -> list[SearchRow]:
        return [
            _row(1, date(2026, 1, 2), "AED", 1200, "debit"),
            _row(2, date(2026, 1, 3), "AED", 200, "credit"),
            _row(3, date(2026, 2, 2), "PKR", 5000, "debit"),
        ]


def test_workspace_lens_keeps_currencies_separate_and_returns_monthly_trend(
    tmp_path: Path,
) -> None:
    app = create_app(tmp_path / "spend-memory.duckdb", tmp_path / "data")
    app.dependency_overrides[get_enrichment_repository] = _Rows

    response = TestClient(app).get("/api/v1/lens")

    assert response.status_code == 200
    assert response.json() == {
        "lens": [
            {
                "currency": "AED",
                "sent_minor": 1200,
                "received_minor": 200,
                "net_minor": -1000,
                "transaction_count": 2,
            },
            {
                "currency": "PKR",
                "sent_minor": 5000,
                "received_minor": 0,
                "net_minor": -5000,
                "transaction_count": 1,
            },
        ],
        "trend": [
            {
                "period_start": "2026-01-01",
                "currency": "AED",
                "sent_minor": 1200,
                "received_minor": 200,
                "net_minor": -1000,
                "transaction_count": 2,
            },
            {
                "period_start": "2026-02-01",
                "currency": "PKR",
                "sent_minor": 5000,
                "received_minor": 0,
                "net_minor": -5000,
                "transaction_count": 1,
            },
        ],
    }
