from dataclasses import dataclass
from datetime import date
from pathlib import Path
from uuid import UUID

from app.main import create_app
from fastapi.testclient import TestClient
from spend_memory.api.dependencies import (
    get_enrichment_repository,
    get_local_workspace_refresh,
)
from spend_memory.enrichment.models import (
    Category,
    CategoryDecision,
    CurrencyFlow,
    Merchant,
    TrustedTransaction,
)
from spend_memory.enrichment.repository import CategorySummary
from spend_memory.enrichment.search import SearchRow


@dataclass(frozen=True)
class _Merchant:
    merchant_id: UUID
    merchant_name: str | None
    status: str
    confidence: float
    method: str
    evidence: dict[str, object]
    transaction_id: UUID
    transaction_date: date


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
        return [
            _Merchant(UUID(int=1), "MetroMart", "suggested", 0.8, "lexical", {"score": 0.8}, UUID(int=10), date(2026, 1, 1)),
            _Merchant(UUID(int=5), "MetroMart February", "suggested", 0.7, "lexical", {"score": 0.7}, UUID(int=11), date(2026, 2, 1)),
        ]

    def list_category_summaries(self, currency: str | None = None) -> list[CategorySummary]:
        assert currency in {None, "AED"}
        return [CategorySummary(Category(UUID(int=2), "Groceries"), (CurrencyFlow("AED", 1200, 200, -1000, 2),))]

    def list_recurring_evidence(self) -> list[_Recurring]:
        return [_Recurring(UUID(int=3), "StreamBox", "monthly", "candidate", 1.0, {"observation_count": 3}, (UUID(int=11), UUID(int=12), UUID(int=13)), "2026-04-01", "2026-04-07")]

    def list_review_evidence(self) -> list[_Review]:
        return [_Review(UUID(int=4), "duplicate", "candidate", 1.0, {"date_distance_days": 0}, (UUID(int=14), UUID(int=15)))]

    def list_counterparty_assignments(self) -> dict[UUID, UUID]:
        return {}

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


def _row(
    identifier: int,
    transaction_date: date,
    description: str,
    amount_minor: int,
    *,
    merchant_name: str | None = None,
    state: str = "unresolved",
    counterparty_label: str | None = None,
    category_id: UUID | None = None,
    category_label: str = "uncategorized",
) -> SearchRow:
    return SearchRow(
        TrustedTransaction(
            UUID(int=identifier), "Everyday", transaction_date, description,
            description.casefold(), "AED", amount_minor, "debit",
        ),
        CategoryDecision(
            category_id,
            category_label,
            "confirmed" if category_id is not None else "unavailable",
        ),
        merchant_name,
        state,
        counterparty_label=counterparty_label,
    )


class _GroupedEntities(_Entities):
    def list_search_rows(self) -> list[SearchRow]:
        return [
            _row(10, date(2026, 1, 1), "METROMART ONE", 700, merchant_name="MetroMart", state="confirmed"),
            _row(12, date(2026, 1, 15), "METROMART TWO", 500, merchant_name="MetroMart", state="confirmed"),
            _row(13, date(2026, 1, 20), "BANK TRANSFER 91", 300),
            _row(14, date(2026, 1, 21), "BANK TRANSFER 91", 400),
            _row(15, date(2026, 2, 1), "METROMART FEB", 900, merchant_name="MetroMart", state="confirmed"),
        ]

    def list_merchant_evidence(self) -> list[_Merchant]:
        return [
            _Merchant(UUID(int=1), "MetroMart", "confirmed", 1.0, "confirmed_alias", {}, UUID(int=identifier), transaction_date)
            for identifier, transaction_date in (
                (10, date(2026, 1, 1)),
                (12, date(2026, 1, 15)),
                (15, date(2026, 2, 1)),
            )
        ]


class _UnavailableGroups(_Entities):
    def list_search_rows(self) -> list[SearchRow]:
        raise RuntimeError("trusted_mart_unavailable")


class _EmptyGroups(_Entities):
    def list_search_rows(self) -> list[SearchRow]:
        return []


class _PeopleEntities(_GroupedEntities):
    def list_search_rows(self) -> list[SearchRow]:
        return [
            _row(
                20,
                date(2026, 1, 7),
                "TRANSFER REFERENCE 7",
                600,
                counterparty_label="Rina",
            )
        ]

    def list_counterparty_assignments(self) -> dict[UUID, UUID]:
        return {UUID(int=20): UUID(int=30)}


class _ScopedEntities(_Entities):
    def list_search_rows(self) -> list[SearchRow]:
        return [
            _row(
                identifier,
                transaction_date,
                f"GROCERY {identifier}",
                100,
                category_id=UUID(int=2),
                category_label="Groceries",
            )
            for identifier, transaction_date in (
                (11, date(2026, 1, 1)),
                (12, date(2026, 1, 10)),
                (13, date(2026, 1, 20)),
                (14, date(2026, 1, 25)),
                (15, date(2026, 2, 1)),
            )
        ]


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


def test_entity_collections_keep_the_start_date_and_exclude_the_end_date(tmp_path: Path) -> None:
    response = _client(tmp_path, _Entities()).get(
        "/api/v1/merchants?after=2026-01-01&before=2026-02-01"
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["merchant_name"] == "MetroMart"


def test_people_places_groups_confirmed_merchants_and_keeps_unresolved_labels_separate(
    tmp_path: Path,
) -> None:
    response = _client(tmp_path, _GroupedEntities()).get(
        "/api/v1/people-places?after=2026-01-01&before=2026-02-01&query=metromart"
    )

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "key": "merchant:00000000-0000-0000-0000-000000000001",
                "label": "MetroMart",
                "kind": "place",
                "status": "confirmed",
                "transactionCount": 2,
                "lastActivityDate": "2026-01-15",
                "flows": [
                    {
                        "currency": "AED",
                        "sent_minor": 1200,
                        "received_minor": 0,
                        "net_minor": -1200,
                        "transaction_count": 2,
                    }
                ],
                "recentTransactionIds": [
                    "00000000-0000-0000-0000-00000000000c",
                    "00000000-0000-0000-0000-00000000000a",
                ],
            }
        ],
        "limit": 50,
        "offset": 0,
        "total": 1,
    }

    all_january = _client(tmp_path, _GroupedEntities()).get(
        "/api/v1/people-places?after=2026-01-01&before=2026-02-01"
    )
    assert [item["kind"] for item in all_january.json()["items"]] == ["place", "unresolved"]
    unresolved = all_january.json()["items"][1]
    assert unresolved["label"] == "Unresolved statement label"
    assert unresolved["transactionCount"] == 2
    assert "description" not in unresolved
    assert "descriptor" not in unresolved


def test_people_places_returns_empty_or_established_unavailable_response(tmp_path: Path) -> None:
    empty = _client(tmp_path, _EmptyGroups()).get("/api/v1/people-places")
    unavailable = _client(tmp_path, _UnavailableGroups()).get("/api/v1/people-places")

    assert empty.status_code == 200
    assert empty.json()["items"] == []
    assert empty.json()["total"] == 0
    assert unavailable.status_code == 503
    assert unavailable.json()["error"]["code"] == "trusted_records_unavailable"


def test_people_places_only_calls_an_assigned_counterparty_a_person(tmp_path: Path) -> None:
    response = _client(tmp_path, _PeopleEntities()).get("/api/v1/people-places")

    assert response.status_code == 200
    assert response.json()["items"][0]["kind"] == "person"
    assert response.json()["items"][0]["label"] == "Rina"
    assert response.json()["items"][0]["key"] == (
        "counterparty:00000000-0000-0000-0000-00000000001e"
    )


def test_categories_and_candidates_use_the_same_complete_scoped_evidence(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path, _ScopedEntities())
    scope = "?after=2026-01-01&before=2026-02-01"

    categories = client.get(f"/api/v1/categories{scope}")
    recurring = client.get(f"/api/v1/recurring{scope}")
    review = client.get(f"/api/v1/review{scope}")

    assert categories.json()["items"] == [
        {
            "category_id": "00000000-0000-0000-0000-000000000002",
            "label": "Groceries",
            "lens": [
                {
                    "currency": "AED",
                    "sent_minor": 400,
                    "received_minor": 0,
                    "net_minor": -400,
                    "transaction_count": 4,
                }
            ],
        }
    ]
    assert recurring.json()["total"] == 1
    assert review.json()["items"] == []


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
