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
        self.aliases: list[tuple[str, UUID]] = []

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

    def create_counterparty(self, label: str) -> Counterparty:
        self.counterparty = Counterparty(UUID(int=10), label)
        return self.counterparty

    def list_counterparties(self) -> list[Counterparty]:
        return [self.counterparty]

    def confirm_counterparty_alias(self, descriptor: str, counterparty_id: UUID) -> None:
        self.aliases.append((descriptor, counterparty_id))


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


def test_counterparty_creation_and_alias_confirmation_are_explicit_actions(
    tmp_path: Path,
) -> None:
    repository = _Counterparties()
    app = create_app(tmp_path / "spend-memory.duckdb", tmp_path / "data")
    app.dependency_overrides[get_enrichment_repository] = lambda: repository
    client = TestClient(app)

    created = client.post("/api/v1/counterparties", json={"label": "Rina Ahmed"})
    alias = client.patch(
        "/api/v1/counterparties/00000000-0000-0000-0000-00000000000a",
        json={"descriptor": "RINA A."},
    )

    assert created.status_code == 201
    assert created.json() == {
        "counterparty_id": "00000000-0000-0000-0000-00000000000a",
        "label": "Rina Ahmed",
    }
    assert alias.status_code == 200
    assert repository.aliases == [("RINA A.", UUID(int=10))]


def test_counterparty_list_and_lens_routes_keep_scope_and_money_typed(tmp_path: Path) -> None:
    client = _client(tmp_path)

    listed = client.get("/api/v1/counterparties?currency=AED")
    lens = client.get("/api/v1/counterparties/00000000-0000-0000-0000-000000000009/lens?after=2026-01-01")

    assert listed.status_code == 200
    assert listed.json() == {
        "items": [{
            "counterparty_id": "00000000-0000-0000-0000-000000000009",
            "label": "Rina",
            "lens": [{"currency": "AED", "sent_minor": 1200, "received_minor": 200, "net_minor": -1000, "transaction_count": 2}],
        }],
        "limit": 50,
        "offset": 0,
        "total": 1,
    }
    assert lens.status_code == 200
    assert lens.json() == {
        "counterparty_id": "00000000-0000-0000-0000-000000000009",
        "label": "Rina",
        "lens": [{"currency": "AED", "sent_minor": 0, "received_minor": 200, "net_minor": 200, "transaction_count": 1}],
        "trend": [{"period_start": "2026-01-01", "currency": "AED", "sent_minor": 0, "received_minor": 200, "net_minor": 200, "transaction_count": 1}],
    }
