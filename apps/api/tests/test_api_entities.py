from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from app.main import create_app
from fastapi.testclient import TestClient
from spend_memory.api.dependencies import (
    get_enrichment_repository,
    get_local_workspace_refresh,
)
from spend_memory.enrichment.models import Category, CurrencyFlow, Merchant
from spend_memory.enrichment.repository import CategorySummary


@dataclass(frozen=True)
class _Merchant:
    merchant_id: UUID
    merchant_name: str | None
    status: str
    confidence: float
    method: str
    evidence: dict[str, object]
    transaction_id: UUID


@dataclass(frozen=True)
class _Recurring:
    candidate_id: UUID
    label: str
    cadence: str
    status: str
    confidence: float
    evidence: dict[str, object]
    transaction_ids: tuple[UUID, ...]
    expected_next_start: str
    expected_next_end: str


@dataclass(frozen=True)
class _Review:
    candidate_id: UUID
    kind: str
    status: str
    confidence: float
    evidence: dict[str, object]
    transaction_ids: tuple[UUID, ...]


class _Entities:
    def __init__(self) -> None:
        self.aliases: list[tuple[str, UUID]] = []
        self.overrides: list[tuple[UUID, UUID]] = []

    def list_merchant_evidence(self) -> list[_Merchant]:
        return [_Merchant(UUID(int=1), "MetroMart", "suggested", 0.8, "lexical", {"score": 0.8}, UUID(int=10))]

    def list_category_summaries(self, currency: str | None = None) -> list[CategorySummary]:
        assert currency in {None, "AED"}
        return [CategorySummary(Category(UUID(int=2), "Groceries"), (CurrencyFlow("AED", 1200, 200, -1000, 2),))]

    def list_recurring_evidence(self) -> list[_Recurring]:
        return [_Recurring(UUID(int=3), "StreamBox", "monthly", "candidate", 1.0, {"observation_count": 3}, (UUID(int=11), UUID(int=12), UUID(int=13)), "2026-04-01", "2026-04-07")]

    def list_review_evidence(self) -> list[_Review]:
        return [_Review(UUID(int=4), "duplicate", "candidate", 1.0, {"date_distance_days": 0}, (UUID(int=14), UUID(int=15)))]

    def get_merchant(self, merchant_id: UUID) -> Merchant | None:
        return Merchant(merchant_id, "MetroMart") if merchant_id == UUID(int=1) else None

    def get_category(self, category_id: UUID) -> Category | None:
        return Category(category_id, "Groceries") if category_id == UUID(int=2) else None

    def confirm_alias(self, descriptor: str, merchant_id: UUID) -> None:
        self.aliases.append((descriptor, merchant_id))

    def assign_merchant_category(self, merchant_id: UUID, category_id: UUID) -> None:
        self.overrides.append((merchant_id, category_id))

    def set_trusted_transaction_category_override(self, transaction_id: UUID, category_id: UUID) -> None:
        self.overrides.append((transaction_id, category_id))


class _Refresh:
    def refresh(self) -> None:
        pass


def _client(tmp_path: Path, repository: _Entities) -> TestClient:
    app = create_app(tmp_path / "spend-memory.duckdb", tmp_path / "data")
    app.dependency_overrides[get_enrichment_repository] = lambda: repository
    app.dependency_overrides[get_local_workspace_refresh] = _Refresh
    return TestClient(app)


def test_entities_expose_candidate_evidence_without_changing_transactions(tmp_path: Path) -> None:
    repository = _Entities()
    client = _client(tmp_path, repository)

    merchants = client.get("/api/v1/merchants")
    categories = client.get("/api/v1/categories")
    recurring = client.get("/api/v1/recurring")
    review = client.get("/api/v1/review")

    assert merchants.json()["items"][0]["status"] == "suggested"
    assert merchants.json()["items"][0]["evidence"] == {"score": 0.8}
    assert categories.json()["items"] == [{"category_id": "00000000-0000-0000-0000-000000000002", "label": "Groceries", "lens": [{"currency": "AED", "sent_minor": 1200, "received_minor": 200, "net_minor": -1000, "transaction_count": 2}]}]
    assert recurring.json()["items"][0]["transaction_ids"] == [
        "00000000-0000-0000-0000-00000000000b",
        "00000000-0000-0000-0000-00000000000c",
        "00000000-0000-0000-0000-00000000000d",
    ]
    assert review.json()["items"][0]["kind"] == "duplicate"
    assert recurring.json()["items"][0]["expected_next_start"] == "2026-04-01"
    assert repository.aliases == repository.overrides == []


def test_entity_collections_have_typed_filters_and_sorting(tmp_path: Path) -> None:
    response = _client(tmp_path, _Entities()).get(
        "/api/v1/merchants?status=suggested&sort=confidence&order=asc"
    )

    assert response.status_code == 200
    assert response.json()["items"][0]["status"] == "suggested"


def test_entity_corrections_only_write_local_annotations(tmp_path: Path) -> None:
    repository = _Entities()
    client = _client(tmp_path, repository)

    merchant = client.patch(
        "/api/v1/merchants/00000000-0000-0000-0000-000000000001",
        json={"descriptor": "METRO MART", "category_id": "00000000-0000-0000-0000-000000000002"},
    )
    transaction = client.patch(
        "/api/v1/transactions/00000000-0000-0000-0000-00000000000a",
        json={"category_id": "00000000-0000-0000-0000-000000000002"},
    )

    assert merchant.status_code == transaction.status_code == 200
    assert repository.aliases == [("METRO MART", UUID(int=1))]
    assert repository.overrides == [(UUID(int=1), UUID(int=2)), (UUID(int=10), UUID(int=2))]
