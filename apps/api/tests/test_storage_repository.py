from __future__ import annotations

import importlib
from hashlib import sha256
from pathlib import Path

import duckdb
import fitz
import pytest
from spend_memory.ingestion.base import ParsedRawTransaction

CSV_DOCUMENT = (
    b"posted_date,description,amount\n"
    b"2026-01-01,Synthetic test purchase,-1200\n"
)


class StubParser:
    parser_id = "stub-parser"

    def __init__(
        self,
        version: str = "1.0",
        transactions: list[ParsedRawTransaction] | None = None,
    ) -> None:
        self.version = version
        self.parse_calls = 0
        self._transactions = transactions or [
            ParsedRawTransaction(
                date_text="2026-01-01",
                description_text="Synthetic test purchase",
                amount_text="-1200",
                currency_text="AED",
                source_page=None,
                source_row=2,
                source_text="2026-01-01,Synthetic test purchase,-1200",
                extraction_method="delimited_text",
                raw_account_identity="SYNTHETIC-AED-1",
                raw_account_reference="ending-0001",
                raw_balance_text="8800",
                extraction_confidence=0.95,
            )
        ]

    def can_parse(self, document: bytes, filename: str) -> float:
        return 1.0

    def parse(self, document: bytes) -> list[ParsedRawTransaction]:
        self.parse_calls += 1
        return self._transactions


class FailingParser(StubParser):
    def parse(self, document: bytes) -> list[ParsedRawTransaction]:
        self.parse_calls += 1
        raise RuntimeError("SENSITIVE-STATEMENT-DETAIL")


def _repository_module():
    try:
        return importlib.import_module("spend_memory.storage.repository")
    except ModuleNotFoundError:
        pytest.fail("storage repository is not implemented")


def _pdf_with_pages(page_count: int) -> bytes:
    with fitz.open() as pdf:
        for _ in range(page_count):
            pdf.new_page()
        return pdf.tobytes()


def test_initial_migration_is_transactional_and_idempotent(tmp_path: Path) -> None:
    repository = _repository_module()
    database_path = tmp_path / "spend-memory.duckdb"

    repository.apply_migrations(database_path)
    repository.apply_migrations(database_path)

    with duckdb.connect(str(database_path), read_only=True) as connection:
        versions = connection.execute(
            "SELECT version FROM storage_migrations ORDER BY version"
        ).fetchall()
        tables = {
            row[0]
            for row in connection.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'main'
                """
            ).fetchall()
        }

    assert versions == [("0001_import_storage",)]
    assert {
        "source_documents",
        "import_runs",
        "raw_transactions",
        "import_errors",
    } <= tables


def test_source_document_identity_is_the_sha256_of_original_bytes(
    tmp_path: Path,
) -> None:
    repository = _repository_module()
    store = repository.ImportRepository(
        database_path=tmp_path / "spend-memory.duckdb",
        data_directory=tmp_path / "data",
    )

    first = store.import_document(
        document=CSV_DOCUMENT,
        filename="first-name.csv",
        declared_mime_type="text/csv",
        parser=StubParser(version="1.0"),
    )
    second = store.import_document(
        document=CSV_DOCUMENT,
        filename="another-name.csv",
        declared_mime_type="text/csv",
        parser=StubParser(version="2.0"),
    )

    with duckdb.connect(str(store.database_path), read_only=True) as connection:
        documents = connection.execute(
            "SELECT document_id, sha256_hex FROM source_documents"
        ).fetchall()

    assert first.document_id == second.document_id
    assert documents == [(first.document_id, sha256(CSV_DOCUMENT).hexdigest())]


def test_same_document_and_parser_version_is_idempotent(tmp_path: Path) -> None:
    repository = _repository_module()
    store = repository.ImportRepository(
        database_path=tmp_path / "spend-memory.duckdb",
        data_directory=tmp_path / "data",
    )
    parser = StubParser(version="1.0")

    first = store.import_document(
        document=CSV_DOCUMENT,
        filename="statement.csv",
        declared_mime_type="text/csv",
        parser=parser,
    )
    second = store.import_document(
        document=CSV_DOCUMENT,
        filename="statement.csv",
        declared_mime_type="text/csv",
        parser=parser,
    )

    with duckdb.connect(str(store.database_path), read_only=True) as connection:
        counts = connection.execute(
            """
            SELECT
                (SELECT count(*) FROM source_documents),
                (SELECT count(*) FROM import_runs),
                (SELECT count(*) FROM raw_transactions)
            """
        ).fetchone()
        active_runs = connection.execute(
            "SELECT run_id FROM import_runs WHERE is_active"
        ).fetchall()

    assert second == repository.ImportResult(
        document_id=first.document_id,
        run_id=first.run_id,
        transaction_count=1,
        was_already_imported=True,
    )
    assert parser.parse_calls == 1
    assert counts == (1, 1, 1)
    assert active_runs == [(first.run_id,)]


def test_new_parser_version_reprocesses_and_is_the_only_active_run(
    tmp_path: Path,
) -> None:
    repository = _repository_module()
    store = repository.ImportRepository(
        database_path=tmp_path / "spend-memory.duckdb",
        data_directory=tmp_path / "data",
    )
    version_one = StubParser(version="1.0")
    version_two = StubParser(
        version="2.0",
        transactions=[
            ParsedRawTransaction(
                date_text=" 2026/01/01 ",
                description_text="SYNTHETIC TEST PURCHASE  ",
                amount_text="AED (1,200.00)",
                currency_text=" aed ",
                source_page=3,
                source_row=17,
                source_text=" 2026/01/01 | SYNTHETIC TEST PURCHASE | (1,200.00) ",
                extraction_method="embedded_text",
                raw_account_identity=" RAW ACCOUNT 01 ",
                raw_account_reference=" ending 0001 ",
                raw_balance_text="AED 8,800.00 CR",
                extraction_confidence=0.73,
            )
        ],
    )

    first = store.import_document(
        document=CSV_DOCUMENT,
        filename="statement.csv",
        declared_mime_type="text/csv",
        parser=version_one,
    )
    second = store.import_document(
        document=CSV_DOCUMENT,
        filename="statement.csv",
        declared_mime_type="text/csv",
        parser=version_two,
    )
    repeated_old_version = store.import_document(
        document=CSV_DOCUMENT,
        filename="statement.csv",
        declared_mime_type="text/csv",
        parser=version_one,
    )

    with duckdb.connect(str(store.database_path), read_only=True) as connection:
        runs = connection.execute(
            """
            SELECT run_id, parser_version, is_active
            FROM import_runs
            ORDER BY parser_version
            """
        ).fetchall()
        second_raw_values = connection.execute(
            """
            SELECT
                d.sha256_hex,
                r.parser_id,
                r.parser_version,
                t.source_ordinal,
                t.date_text,
                t.description_text,
                t.amount_text,
                t.currency_text,
                t.source_page,
                t.source_row,
                t.source_text,
                t.extraction_method,
                t.raw_account_identity,
                t.raw_account_reference,
                t.raw_balance_text,
                t.extraction_confidence
            FROM raw_transactions t
            JOIN import_runs r ON r.run_id = t.import_run_id
            JOIN source_documents d ON d.document_id = r.document_id
            WHERE t.import_run_id = ?
            """,
            [second.run_id],
        ).fetchone()

    assert first.run_id != second.run_id
    assert repeated_old_version.run_id == first.run_id
    assert repeated_old_version.was_already_imported is True
    assert version_one.parse_calls == 1
    assert version_two.parse_calls == 1
    assert runs == [
        (first.run_id, "1.0", False),
        (second.run_id, "2.0", True),
    ]
    assert second_raw_values == (
        sha256(CSV_DOCUMENT).hexdigest(),
        "stub-parser",
        "2.0",
        1,
        " 2026/01/01 ",
        "SYNTHETIC TEST PURCHASE  ",
        "AED (1,200.00)",
        " aed ",
        3,
        17,
        " 2026/01/01 | SYNTHETIC TEST PURCHASE | (1,200.00) ",
        "embedded_text",
        " RAW ACCOUNT 01 ",
        " ending 0001 ",
        "AED 8,800.00 CR",
        0.73,
    )


def test_original_document_bytes_are_stored_under_a_sha_derived_filename(
    tmp_path: Path,
) -> None:
    repository = _repository_module()
    store = repository.ImportRepository(
        database_path=tmp_path / "spend-memory.duckdb",
        data_directory=tmp_path / "data",
    )

    result = store.import_document(
        document=CSV_DOCUMENT,
        filename="statement.csv",
        declared_mime_type="text/csv",
        parser=StubParser(),
    )
    expected_filename = f"{sha256(CSV_DOCUMENT).hexdigest()}.csv"

    with duckdb.connect(str(store.database_path), read_only=True) as connection:
        stored = connection.execute(
            """
            SELECT storage_filename, byte_size
            FROM source_documents
            WHERE document_id = ?
            """,
            [result.document_id],
        ).fetchone()

    assert stored == (expected_filename, len(CSV_DOCUMENT))
    assert sorted(path.name for path in store.data_directory.iterdir()) == [
        expected_filename
    ]
    assert (store.data_directory / expected_filename).read_bytes() == CSV_DOCUMENT


def test_parser_failure_is_recorded_without_partial_import_data(
    tmp_path: Path,
) -> None:
    repository = _repository_module()
    store = repository.ImportRepository(
        database_path=tmp_path / "spend-memory.duckdb",
        data_directory=tmp_path / "data",
    )

    with pytest.raises(repository.ImportRepositoryError) as caught:
        store.import_document(
            document=CSV_DOCUMENT,
            filename="statement.csv",
            declared_mime_type="text/csv",
            parser=FailingParser(version="7.2"),
        )

    with duckdb.connect(str(store.database_path), read_only=True) as connection:
        import_counts = connection.execute(
            """
            SELECT
                (SELECT count(*) FROM source_documents),
                (SELECT count(*) FROM import_runs),
                (SELECT count(*) FROM raw_transactions)
            """
        ).fetchone()
        errors = connection.execute(
            """
            SELECT
                document_sha256_hex,
                original_filename,
                declared_mime_type,
                parser_id,
                parser_version,
                error_type,
                error_message
            FROM import_errors
            """
        ).fetchall()

    assert caught.value.code == "parser_failed"
    assert str(caught.value) == "parser_failed"
    assert caught.value.__cause__ is None
    assert "SENSITIVE-STATEMENT-DETAIL" not in str(caught.value)
    assert import_counts == (0, 0, 0)
    assert errors == [
        (
            sha256(CSV_DOCUMENT).hexdigest(),
            "statement.csv",
            "text/csv",
            "stub-parser",
            "7.2",
            "parser_failed",
            "parser_failed",
        )
    ]
    assert not store.data_directory.exists()


def test_failed_reprocessing_does_not_replace_the_active_run(
    tmp_path: Path,
) -> None:
    repository = _repository_module()
    store = repository.ImportRepository(
        database_path=tmp_path / "spend-memory.duckdb",
        data_directory=tmp_path / "data",
    )
    active = store.import_document(
        document=CSV_DOCUMENT,
        filename="statement.csv",
        declared_mime_type="text/csv",
        parser=StubParser(version="1.0"),
    )

    with pytest.raises(repository.ImportRepositoryError):
        store.import_document(
            document=CSV_DOCUMENT,
            filename="statement.csv",
            declared_mime_type="text/csv",
            parser=FailingParser(version="2.0"),
        )

    with duckdb.connect(str(store.database_path), read_only=True) as connection:
        runs = connection.execute(
            "SELECT run_id, parser_version, is_active FROM import_runs"
        ).fetchall()
        counts = connection.execute(
            """
            SELECT
                (SELECT count(*) FROM raw_transactions),
                (SELECT count(*) FROM import_errors)
            """
        ).fetchone()

    assert runs == [(active.run_id, "1.0", True)]
    assert counts == (1, 1)


def test_storage_failure_rolls_back_database_rows_and_source_file(
    tmp_path: Path,
) -> None:
    repository = _repository_module()
    store = repository.ImportRepository(
        database_path=tmp_path / "spend-memory.duckdb",
        data_directory=tmp_path / "data",
    )
    valid = StubParser()._transactions[0]
    invalid = ParsedRawTransaction(
        date_text="2026-01-02",
        description_text="Cannot be bound",
        amount_text="-1",
        currency_text="AED",
        source_page=object(),  # type: ignore[arg-type]
        source_row=3,
        source_text="invalid persisted value",
        extraction_method="delimited_text",
    )

    with pytest.raises(repository.ImportRepositoryError) as caught:
        store.import_document(
            document=CSV_DOCUMENT,
            filename="statement.csv",
            declared_mime_type="text/csv",
            parser=StubParser(transactions=[valid, invalid]),
        )

    with duckdb.connect(str(store.database_path), read_only=True) as connection:
        counts = connection.execute(
            """
            SELECT
                (SELECT count(*) FROM source_documents),
                (SELECT count(*) FROM import_runs),
                (SELECT count(*) FROM raw_transactions),
                (SELECT count(*) FROM import_errors)
            """
        ).fetchone()
        error_type = connection.execute(
            "SELECT error_type FROM import_errors"
        ).fetchone()

    assert caught.value.code == "storage_failed"
    assert caught.value.__cause__ is None
    assert counts == (0, 0, 0, 1)
    assert error_type == ("storage_failed",)
    assert list(store.data_directory.iterdir()) == []


def test_oversized_document_is_rejected_before_parser_or_persistence(
    tmp_path: Path,
) -> None:
    repository = _repository_module()
    parser = StubParser()
    store = repository.ImportRepository(
        database_path=tmp_path / "spend-memory.duckdb",
        data_directory=tmp_path / "data",
        limits=repository.ImportLimits(max_document_bytes=8, max_pdf_pages=20),
    )

    with pytest.raises(repository.ImportRepositoryError) as caught:
        store.import_document(
            document=CSV_DOCUMENT,
            filename="statement.csv",
            declared_mime_type="text/csv",
            parser=parser,
        )

    with duckdb.connect(str(store.database_path), read_only=True) as connection:
        counts = connection.execute(
            """
            SELECT
                (SELECT count(*) FROM source_documents),
                (SELECT count(*) FROM import_runs),
                (SELECT count(*) FROM raw_transactions),
                (SELECT count(*) FROM import_errors)
            """
        ).fetchone()

    assert caught.value.code == "document_too_large"
    assert parser.parse_calls == 0
    assert counts == (0, 0, 0, 0)
    assert not store.data_directory.exists()


@pytest.mark.parametrize(
    ("document", "declared_mime_type", "expected_code"),
    [
        (CSV_DOCUMENT, "application/octet-stream", "unsupported_mime_type"),
        (b"%PDF-1.7\nsynthetic", "text/csv", "mime_type_mismatch"),
        (CSV_DOCUMENT, "application/pdf", "mime_type_mismatch"),
        (b"\x00\x01\x02", "text/csv", "mime_type_mismatch"),
    ],
)
def test_mime_safeguards_reject_before_parser_or_persistence(
    tmp_path: Path,
    document: bytes,
    declared_mime_type: str,
    expected_code: str,
) -> None:
    repository = _repository_module()
    parser = StubParser()
    store = repository.ImportRepository(
        database_path=tmp_path / "spend-memory.duckdb",
        data_directory=tmp_path / "data",
    )

    with pytest.raises(repository.ImportRepositoryError) as caught:
        store.import_document(
            document=document,
            filename="statement.csv",
            declared_mime_type=declared_mime_type,
            parser=parser,
        )

    with duckdb.connect(str(store.database_path), read_only=True) as connection:
        counts = connection.execute(
            """
            SELECT
                (SELECT count(*) FROM source_documents),
                (SELECT count(*) FROM import_runs),
                (SELECT count(*) FROM import_errors)
            """
        ).fetchone()

    assert caught.value.code == expected_code
    assert parser.parse_calls == 0
    assert counts == (0, 0, 0)
    assert not store.data_directory.exists()


def test_pdf_page_limit_is_checked_before_parser_or_persistence(
    tmp_path: Path,
) -> None:
    repository = _repository_module()
    parser = StubParser()
    store = repository.ImportRepository(
        database_path=tmp_path / "spend-memory.duckdb",
        data_directory=tmp_path / "data",
        limits=repository.ImportLimits(
            max_document_bytes=20 * 1024 * 1024,
            max_pdf_pages=1,
        ),
    )

    with pytest.raises(repository.ImportRepositoryError) as caught:
        store.import_document(
            document=_pdf_with_pages(2),
            filename="statement.pdf",
            declared_mime_type="application/pdf",
            parser=parser,
        )

    with duckdb.connect(str(store.database_path), read_only=True) as connection:
        counts = connection.execute(
            """
            SELECT
                (SELECT count(*) FROM source_documents),
                (SELECT count(*) FROM import_runs),
                (SELECT count(*) FROM import_errors)
            """
        ).fetchone()

    assert caught.value.code == "pdf_page_limit"
    assert parser.parse_calls == 0
    assert counts == (0, 0, 0)
    assert not store.data_directory.exists()


@pytest.mark.parametrize(
    "filename",
    [
        "../statement.csv",
        "nested/statement.csv",
        r"..\statement.csv",
        "/tmp/statement.csv",
        "",
    ],
)
def test_path_traversal_filename_is_rejected_before_parser_or_persistence(
    tmp_path: Path,
    filename: str,
) -> None:
    repository = _repository_module()
    parser = StubParser()
    store = repository.ImportRepository(
        database_path=tmp_path / "spend-memory.duckdb",
        data_directory=tmp_path / "data",
    )

    with pytest.raises(repository.ImportRepositoryError) as caught:
        store.import_document(
            document=CSV_DOCUMENT,
            filename=filename,
            declared_mime_type="text/csv",
            parser=parser,
        )

    with duckdb.connect(str(store.database_path), read_only=True) as connection:
        counts = connection.execute(
            """
            SELECT
                (SELECT count(*) FROM source_documents),
                (SELECT count(*) FROM import_runs),
                (SELECT count(*) FROM import_errors)
            """
        ).fetchone()

    assert caught.value.code == "unsafe_filename"
    assert parser.parse_calls == 0
    assert counts == (0, 0, 0)
    assert not store.data_directory.exists()
