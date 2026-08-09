from pathlib import Path

from app.main import create_app
from fastapi.testclient import TestClient

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_normal_import_makes_trusted_activity_available_without_a_manual_refresh(
    tmp_path: Path,
) -> None:
    client = TestClient(create_app(tmp_path / "spend-memory.duckdb", tmp_path / "data"))
    source = REPOSITORY_ROOT / "sample_data/source/aed_january_2026.csv"

    imported = client.post(
        "/api/v1/imports",
        files={"file": (source.name, source.read_bytes(), "text/csv")},
    )
    trusted = client.get("/api/v1/transactions")

    assert imported.status_code == 201
    assert trusted.status_code == 200
    assert trusted.json()["total"] == 18


def test_demo_reset_makes_trusted_activity_available_without_a_manual_refresh(
    tmp_path: Path,
) -> None:
    client = TestClient(create_app(tmp_path / "spend-memory.duckdb", tmp_path / "data"))

    reset = client.post("/api/v1/demo/reset")
    trusted = client.get("/api/v1/transactions")

    assert reset.status_code == 200
    assert trusted.status_code == 200
    assert trusted.json()["total"] == 18
