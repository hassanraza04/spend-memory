from datetime import date
from pathlib import Path
from uuid import UUID

from app.main import create_app
from fastapi.testclient import TestClient
from spend_memory.api.dependencies import get_enrichment_repository
from spend_memory.enrichment.models import TrustedTransaction
from spend_memory.enrichment.periods import PeriodRow


class _Periods:
    def list_period_rows(self, start: date, end: date, account: str, currency: str) -> list[PeriodRow]:
        rows = {
            (date(2026, 1, 1), date(2026, 2, 1)): [
                PeriodRow(TrustedTransaction(UUID(int=1), account, date(2026, 1, 10), "Metro", "metro", currency, 100, "debit"), merchant_name="MetroMart")
            ],
            (date(2026, 2, 1), date(2026, 3, 1)): [
                PeriodRow(TrustedTransaction(UUID(int=2), account, date(2026, 2, 10), "Metro", "metro", currency, 250, "debit"), merchant_name="MetroMart")
            ],
        }
        return rows[(start, end)]


def test_comparison_returns_exact_reconciled_contribution_lineage(tmp_path: Path) -> None:
    app = create_app(tmp_path / "spend-memory.duckdb", tmp_path / "data")
    app.dependency_overrides[get_enrichment_repository] = _Periods

    response = TestClient(app).get(
        "/api/v1/comparisons?before_start=2026-01-01&before_end=2026-02-01&after_start=2026-02-01&after_end=2026-03-01&account=AED-001&currency=AED"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["difference_net_amount_minor"] == -150
    assert body["contribution_total_minor"] + body["remainder_minor"] == -150
    assert body["contributions"][0]["before_transaction_ids"] == ["00000000-0000-0000-0000-000000000001"]
    assert body["contributions"][0]["after_transaction_ids"] == ["00000000-0000-0000-0000-000000000002"]


def test_comparison_rejects_overlapping_periods(tmp_path: Path) -> None:
    response = TestClient(create_app(tmp_path / "spend-memory.duckdb", tmp_path / "data")).get(
        "/api/v1/comparisons?before_start=2026-01-01&before_end=2026-02-15&after_start=2026-02-01&after_end=2026-03-01&account=AED-001&currency=AED"
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_filter"


def test_demo_reset_returns_exact_april_versus_march_explanation(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "spend-memory.duckdb", tmp_path / "data"))

    assert client.post("/api/v1/demo/reset").status_code == 200
    response = client.get(
        "/api/v1/comparisons"
        "?before_start=2026-03-01&before_end=2026-04-01"
        "&after_start=2026-04-01&after_end=2026-05-01"
        "&account=AED-SYNTH-001&currency=AED"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["difference_net_amount_minor"] == -36243
    assert [
        (item["label"], item["amount_minor"]) for item in body["contributions"]
    ] == [("Quick Cart", -26920), ("nova bazaar", -17800), ("transfer received", 12500)]
    assert body["text"] == (
        "Net activity was 36243 minor units lower than the previous period. "
        "Quick Cart accounted for 26920 minor units. "
        "nova bazaar accounted for 17800 minor units. "
        "transfer received accounted for 12500 minor units. "
        "Other activity accounted for 4023 minor units."
    )
