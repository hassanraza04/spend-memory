from pathlib import Path
from threading import Event, Thread

import duckdb
from app.main import create_app
from fastapi.testclient import TestClient
from spend_memory.api.dependencies import (
    LocalDataService,
    LocalSettings,
    get_local_data_service,
)
from spend_memory.storage.repository import database_write_lock


class _LocalData:
    def __init__(self, real_import: bool = False) -> None:
        self.real_import = real_import
        self.deleted = False
        self.reset = False

    def reset_demo(self) -> None:
        if self.real_import:
            raise ValueError("non_demo_imports_present")
        self.reset = True

    def delete(self) -> None:
        self.deleted = True


def _client(tmp_path: Path, service: _LocalData) -> TestClient:
    app = create_app(tmp_path / "spend-memory.duckdb", tmp_path / "data")
    app.dependency_overrides[get_local_data_service] = lambda: service
    return TestClient(app)


def test_demo_reset_rejects_workspace_with_a_real_import(tmp_path: Path) -> None:
    response = _client(tmp_path, _LocalData(real_import=True)).post("/api/v1/demo/reset")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "non_demo_imports_present"


def test_demo_reset_creates_marked_synthetic_records(tmp_path: Path) -> None:
    database_path = tmp_path / "spend-memory.duckdb"
    client = TestClient(create_app(database_path, tmp_path / "data"))

    response = client.post("/api/v1/demo/reset")

    assert response.status_code == 200
    with duckdb.connect(str(database_path), read_only=True) as connection:
        document = connection.execute(
            "SELECT original_filename, is_demo FROM source_documents"
        ).fetchone()
    assert document == ("aed_january_2026.csv", True)

    context = client.get("/api/v1/workspace-context")
    transactions = client.get("/api/v1/transactions?limit=100")

    assert context.status_code == transactions.status_code == 200
    assert context.json() == {
        "firstTransactionDate": "2026-01-01",
        "lastTransactionDate": "2026-04-30",
        "latestMonthStart": "2026-04-01",
        "latestMonthEnd": "2026-05-01",
        "accounts": [{"account": "AED-SYNTH-001", "currencies": ["AED"]}],
    }
    assert transactions.json()["total"] == 28
    assert {
        item["transaction_date"] for item in transactions.json()["items"]
    } >= {"2026-01-01", "2026-04-30"}


def test_demo_reset_builds_meaningful_enrichment_evidence(tmp_path: Path) -> None:
    database_path = tmp_path / "spend-memory.duckdb"
    client = TestClient(create_app(database_path, tmp_path / "data"))

    response = client.post("/api/v1/demo/reset")

    assert response.status_code == 200
    transactions = client.get("/api/v1/transactions?limit=100").json()["items"]
    merchant_evidence = client.get("/api/v1/merchants?limit=100").json()["items"]
    categories = client.get("/api/v1/categories?limit=100").json()["items"]
    recurring = client.get("/api/v1/recurring?limit=100").json()["items"]
    review = client.get("/api/v1/review?limit=100").json()["items"]
    comparison = client.get(
        "/api/v1/comparisons"
        "?before_start=2026-03-01&before_end=2026-04-01"
        "&after_start=2026-04-01&after_end=2026-05-01"
        "&account=AED-SYNTH-001&currency=AED"
    )

    confirmed_names = {
        item["merchant_name"]
        for item in merchant_evidence
        if item["status"] == "confirmed"
    }
    unresolved_descriptions = {
        item["description"] for item in transactions if item["state"] == "unresolved"
    }
    streambox = sorted(
        (item for item in transactions if item["merchant"] == "Streambox"),
        key=lambda item: item["transaction_date"],
    )
    duplicates = [item for item in review if item["kind"] == "duplicate"]

    assert confirmed_names == {
        "Brew Lab",
        "MetroMart",
        "Orbit Fuel",
        "PixelBooks",
        "Quick Cart",
        "Streambox",
    }
    assert {item["label"] for item in categories} == {
        "Books",
        "Dining",
        "Entertainment",
        "Groceries",
        "Shopping",
        "Transport",
    }
    assert {"HBR PHARM", "NOVA BAZAAR"} <= unresolved_descriptions
    assert len(streambox) == 4
    assert [item["transaction_date"] for item in streambox] == [
        "2026-01-03",
        "2026-02-03",
        "2026-03-03",
        "2026-04-03",
    ]
    assert max(item["amount_minor"] for item in streambox) * 10 >= (
        max(item["amount_minor"] for item in streambox)
        - min(item["amount_minor"] for item in streambox)
    ) * 100
    assert len(recurring) == 1
    assert recurring[0]["label"] == "Streambox"
    assert recurring[0]["cadence"] == "monthly"
    assert recurring[0]["evidence"]["observation_count"] == 4
    assert len(recurring[0]["transaction_ids"]) == 4
    assert len(duplicates) == 1
    duplicate = duplicates[0]
    duplicate_rows = [
        item for item in transactions if item["transaction_id"] in duplicate["transaction_ids"]
    ]
    assert len(duplicate_rows) == 2
    assert {item["transaction_date"] for item in duplicate_rows} == {"2026-04-12"}
    assert {item["amount_minor"] for item in duplicate_rows} == {12500}
    assert {item["merchant"] for item in duplicate_rows} == {"MetroMart"}
    assert comparison.status_code == 200
    assert comparison.json()["difference_net_amount_minor"] != 0
    assert comparison.json()["contributions"]


def test_demo_reset_twice_does_not_duplicate_seeded_records(tmp_path: Path) -> None:
    database_path = tmp_path / "spend-memory.duckdb"
    client = TestClient(create_app(database_path, tmp_path / "data"))

    assert client.post("/api/v1/demo/reset").status_code == 200
    assert client.post("/api/v1/demo/reset").status_code == 200

    with duckdb.connect(str(database_path), read_only=True) as connection:
        counts = connection.execute(
            """
            SELECT
                (SELECT count(*) FROM source_documents),
                (SELECT count(*) FROM raw_transactions),
                (SELECT count(*) FROM merchants),
                (SELECT count(*) FROM merchant_aliases),
                (SELECT count(*) FROM merchant_currency_observations),
                (SELECT count(*) FROM categories),
                (SELECT count(*) FROM merchant_category_assignments)
            """
        ).fetchone()
        distinct_counts = connection.execute(
            """
            SELECT
                (SELECT count(DISTINCT merchant_name) FROM merchants),
                (SELECT count(DISTINCT normalized_descriptor) FROM merchant_aliases),
                (SELECT count(DISTINCT category_label) FROM categories)
            """
        ).fetchone()

    assert counts == (1, 28, 6, 7, 6, 6, 6)
    assert distinct_counts == (6, 7, 6)


def test_demo_reset_rejects_a_user_imported_canonical_csv(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "spend-memory.duckdb", tmp_path / "data"))
    document = (
        b"transaction_id,posted_date,account_id,currency,amount_minor,description,transaction_type\n"
        b"SYN-00001,2026-01-01,AED-SYNTH-001,AED,-1200,User imported row,debit\n"
    )

    imported = client.post(
        "/api/v1/imports",
        files={"file": ("user.csv", document, "text/csv")},
    )
    reset = client.post("/api/v1/demo/reset")

    assert imported.status_code == 201
    assert reset.status_code == 409
    assert reset.json()["error"]["code"] == "non_demo_imports_present"


def test_local_data_deletion_requires_the_exact_confirmation(tmp_path: Path) -> None:
    service = _LocalData()
    client = _client(tmp_path, service)

    rejected = client.request("DELETE", "/api/v1/local-data", json={"confirmation": "delete local data"})
    extra = client.request(
        "DELETE",
        "/api/v1/local-data",
        json={"confirmation": "DELETE LOCAL DATA", "also_delete": "no"},
    )
    accepted = client.request("DELETE", "/api/v1/local-data", json={"confirmation": "DELETE LOCAL DATA"})

    assert rejected.status_code == 422
    assert extra.status_code == 422
    assert accepted.status_code == 200
    assert accepted.json() == {"status": "deleted"}
    assert service.deleted is True


def test_local_deletion_waits_for_an_active_database_writer(tmp_path: Path) -> None:
    database_path = tmp_path / "spend-memory.duckdb"
    service = LocalDataService(LocalSettings(database_path, tmp_path / "data", tmp_path))
    writer_started = Event()
    release_writer = Event()
    deletion_finished = Event()

    def hold_writer() -> None:
        with database_write_lock(database_path):
            writer_started.set()
            release_writer.wait()

    writer = Thread(target=hold_writer)
    writer.start()
    assert writer_started.wait(1)

    deleter = Thread(target=lambda: (service.delete(), deletion_finished.set()))
    deleter.start()
    try:
        assert not deletion_finished.wait(0.1)
    finally:
        release_writer.set()
        writer.join()
        deleter.join()

    assert deletion_finished.is_set()
    assert database_path.with_name(f".{database_path.name}.write.lock").exists()


def test_local_deletion_rejects_outside_or_symlinked_data_paths(tmp_path: Path) -> None:
    root = tmp_path / "app-data"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")

    for data_directory in (outside, root / "link"):
        if data_directory.name == "link":
            data_directory.symlink_to(outside, target_is_directory=True)
        service = LocalDataService(
            LocalSettings(root / "spend-memory.duckdb", data_directory, root)
        )

        try:
            service.delete()
        except ValueError as error:
            assert str(error) == "unsafe_local_data_path"
        else:
            raise AssertionError("outside path was deleted")
        assert sentinel.read_text(encoding="utf-8") == "keep"
