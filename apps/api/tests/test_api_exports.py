from datetime import date
from pathlib import Path
from uuid import UUID

from app.main import create_app
from fastapi.testclient import TestClient
from spend_memory.api.dependencies import get_enrichment_repository
from spend_memory.enrichment.models import CategoryDecision, TrustedTransaction
from spend_memory.enrichment.search import SearchRow


class _Rows:
    def list_search_rows(self) -> list[SearchRow]:
        return [
            SearchRow(
                TrustedTransaction(UUID(int=1), "AED-001", date(2026, 1, 1), "=SUM(A1:A2)", "sum a1 a2", "AED", 1200, "debit"),
                CategoryDecision(None, "+Groceries", "unavailable"),
                "@Metro",
                "unresolved",
                source_document="-statement.csv",
                source_ordinal=1,
                source_text="=source",
            )
        ]


def test_csv_export_uses_trusted_scope_and_neutralizes_formula_cells(tmp_path: Path) -> None:
    app = create_app(tmp_path / "spend-memory.duckdb", tmp_path / "data")
    app.dependency_overrides[get_enrichment_repository] = _Rows

    response = TestClient(app).get("/api/v1/exports/transactions.csv?account=AED-001")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment; filename=transactions.csv" == response.headers["content-disposition"]
    assert "'=SUM(A1:A2)" in response.text
    assert "'+Groceries" in response.text
    assert "'@Metro" in response.text
    assert "'-statement.csv" in response.text
