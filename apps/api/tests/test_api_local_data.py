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
        transaction_count = connection.execute("SELECT count(*) FROM raw_transactions").fetchone()
    assert document == ("aed_january_2026.csv", True)
    assert transaction_count == (18,)


def test_demo_reset_uses_the_reconcilable_synthetic_statement(tmp_path: Path) -> None:
    database_path = tmp_path / "spend-memory.duckdb"
    client = TestClient(create_app(database_path, tmp_path / "data"))

    response = client.post("/api/v1/demo/reset")

    assert response.status_code == 200
    with duckdb.connect(str(database_path), read_only=True) as connection:
        document = connection.execute(
            "SELECT original_filename, is_demo FROM source_documents"
        ).fetchone()
        transaction_count = connection.execute("SELECT count(*) FROM raw_transactions").fetchone()
    assert document == ("aed_january_2026.csv", True)
    assert transaction_count == (18,)


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
