from datetime import date
from pathlib import Path
from uuid import UUID

from app.main import create_app
from fastapi.testclient import TestClient
from spend_memory.api.dependencies import get_enrichment_repository
from spend_memory.enrichment.models import Counterparty, TrustedTransaction


class _Counterparties:
    def __init__(self) -> None:
        self.counterparty = Counterparty(UUID(int=9), "Rina")
        self.assigned: list[UUID] = []

    def get_counterparty(self, counterparty_id: UUID) -> Counterparty | None:
        return self.counterparty if counterparty_id == self.counterparty.counterparty_id else None

    def assign_counterparty_transactions(self, _: UUID, transaction_ids: list[UUID]) -> None:
        if UUID(int=99) in transaction_ids:
            raise ValueError("trusted_transaction_required")
        self.assigned.extend(transaction_ids)

    def list_counterparty_transactions(self, _: UUID) -> list[TrustedTransaction]:
        return [
            TrustedTransaction(UUID(int=1), "AED-001", date(2026, 1, 1), "Rina", "rina", "AED", 1200, "debit"),
            TrustedTransaction(UUID(int=2), "AED-001", date(2026, 1, 2), "Rina", "rina", "AED", 200, "credit"),
        ]


def _client(tmp_path: Path) -> TestClient:
    app = create_app(tmp_path / "spend-memory.duckdb", tmp_path / "data")
    app.dependency_overrides[get_enrichment_repository] = _Counterparties
    return TestClient(app)


def test_counterparty_grouping_returns_currency_separated_lens(tmp_path: Path) -> None:
    response = _client(tmp_path).post(
        "/api/v1/counterparties/00000000-0000-0000-0000-000000000009/transactions",
        json={"transaction_ids": ["00000000-0000-0000-0000-000000000001"]},
    )

    assert response.status_code == 200
    assert response.json() == {
        "counterparty_id": "00000000-0000-0000-0000-000000000009",
        "label": "Rina",
        "lens": [{"currency": "AED", "sent_minor": 1200, "received_minor": 200, "net_minor": -1000, "transaction_count": 2}],
    }


def test_counterparty_assignment_rejects_missing_counterparty_duplicate_or_untrusted_rows(tmp_path: Path) -> None:
    client = _client(tmp_path)
    missing = client.post(
        "/api/v1/counterparties/00000000-0000-0000-0000-000000000010/transactions",
        json={"transaction_ids": ["00000000-0000-0000-0000-000000000001"]},
    )
    duplicate = client.post(
        "/api/v1/counterparties/00000000-0000-0000-0000-000000000009/transactions",
        json={"transaction_ids": ["00000000-0000-0000-0000-000000000001", "00000000-0000-0000-0000-000000000001"]},
    )
    untrusted = client.post(
        "/api/v1/counterparties/00000000-0000-0000-0000-000000000009/transactions",
        json={"transaction_ids": ["00000000-0000-0000-0000-000000000063"]},
    )

    assert missing.json()["error"]["code"] == "counterparty_not_found"
    assert duplicate.status_code == 422
    assert untrusted.json()["error"]["code"] == "untrusted_transaction"
