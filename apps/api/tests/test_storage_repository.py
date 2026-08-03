from __future__ import annotations

import importlib
import multiprocessing
import os
import resource
import signal
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from pathlib import Path
from threading import Event, Lock

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


class ConcurrentParser(StubParser):
    def __init__(self) -> None:
        super().__init__()
        self.first_parse_entered = Event()
        self.second_parse_entered = Event()
        self.release_first_parse = Event()
        self._parse_call_lock = Lock()

    def parse(self, document: bytes) -> list[ParsedRawTransaction]:
        with self._parse_call_lock:
            self.parse_calls += 1
            call_number = self.parse_calls
        if call_number == 1:
            self.first_parse_entered.set()
            if not self.release_first_parse.wait(timeout=5):
                raise RuntimeError("concurrency test did not release parser")
        else:
            self.second_parse_entered.set()
        return self._transactions


class SignalingParser(StubParser):
    def __init__(self, version: str) -> None:
        super().__init__(version=version)
        self.parse_entered = Event()

    def parse(self, document: bytes) -> list[ParsedRawTransaction]:
        self.parse_entered.set()
        return super().parse(document)


class IndependentProcessParser(StubParser):
    def __init__(self, parse_count, both_parsers_entered) -> None:
        super().__init__()
        self._shared_parse_count = parse_count
        self._both_parsers_entered = both_parsers_entered

    def parse(self, document: bytes) -> list[ParsedRawTransaction]:
        with self._shared_parse_count.get_lock():
            self._shared_parse_count.value += 1
            if self._shared_parse_count.value == 2:
                self._both_parsers_entered.set()
        self._both_parsers_entered.wait(timeout=1)
        return self._transactions


def _run_independent_process_import(
    database_path: str,
    data_directory: str,
    ready_queue,
    start_import,
    parse_count,
    both_parsers_entered,
    result_queue,
) -> None:
    repository = _repository_module()
    store = repository.ImportRepository(
        database_path=Path(database_path),
        data_directory=Path(data_directory),
    )
    ready_queue.put(True)
    if not start_import.wait(timeout=10):
        result_queue.put(("error", "start_timeout"))
        return

    try:
        result = store._import_document_for_tests(
            document=CSV_DOCUMENT,
            filename="statement.csv",
            declared_mime_type="text/csv",
            parser=IndependentProcessParser(
                parse_count,
                both_parsers_entered,
            ),
        )
    except BaseException as error:  # noqa: BLE001
        result_queue.put(("error", type(error).__name__))
    else:
        result_queue.put(
            (
                "ok",
                str(result.document_id),
                str(result.run_id),
                result.was_already_imported,
            )
        )


def _run_distinct_document_process_import(
    database_path: str,
    data_directory: str,
    document: bytes,
    ready_queue,
    start_import,
    parse_count,
    both_parsers_entered,
    result_queue,
) -> None:
    repository = _repository_module()
    store = repository.ImportRepository(
        database_path=Path(database_path),
        data_directory=Path(data_directory),
    )
    ready_queue.put(True)
    if not start_import.wait(timeout=10):
        result_queue.put(("error", "start_timeout"))
        return

    try:
        result = store._import_document_for_tests(
            document=document,
            filename="statement.csv",
            declared_mime_type="text/csv",
            parser=IndependentProcessParser(parse_count, both_parsers_entered),
        )
    except BaseException as error:  # noqa: BLE001
        result_queue.put(("error", type(error).__name__))
    else:
        result_queue.put(("ok", str(result.document_id), str(result.run_id)))


def _repository_module():
    try:
        module = importlib.import_module("spend_memory.storage.repository")
    except ModuleNotFoundError:
        pytest.fail("storage repository is not implemented")

    class TestImportRepository(module.ImportRepository):
        def _import_document_for_tests(
            self,
            *,
            document: bytes,
            filename: str,
            declared_mime_type: str,
            parser,
        ):
            self.validate_document(
                document=document,
                filename=filename,
                declared_mime_type=declared_mime_type,
            )
            existing = self.find_existing_import(
                document=document,
                filename=filename,
                declared_mime_type=declared_mime_type,
                parser_id=parser.parser_id,
                parser_version=parser.version,
            )
            if existing is not None:
                return existing
            try:
                transactions = parser.parse(document)
            except Exception:  # noqa: BLE001
                self.record_isolated_parse_error(
                    document=document,
                    filename=filename,
                    declared_mime_type=declared_mime_type,
                    parser_id=parser.parser_id,
                    parser_version=parser.version,
                    code="parser_failed",
                )
                raise module.ImportRepositoryError("parser_failed") from None
            return self.store_preparsed_document(
                document=document,
                filename=filename,
                declared_mime_type=declared_mime_type,
                parser_id=parser.parser_id,
                parser_version=parser.version,
                transactions=transactions,
            )

    class TestRepositoryModule:
        ImportRepository = TestImportRepository

        def __getattr__(self, name: str):
            return getattr(module, name)

    return TestRepositoryModule()


def test_repository_exposes_no_direct_parser_import_path(tmp_path) -> None:
    repository = importlib.import_module("spend_memory.storage.repository")
    store = repository.ImportRepository(
        database_path=tmp_path / "spend-memory.duckdb",
        data_directory=tmp_path / "documents",
    )

    assert not hasattr(store, "_import_document_for_tests")


def _pdf_with_pages(page_count: int) -> bytes:
    with fitz.open() as pdf:
        for _ in range(page_count):
            pdf.new_page()
        return pdf.tobytes()


def _report_effective_resource_limits(limits, result_queue) -> None:
    from spend_memory.ingestion.resource_limits import apply_resource_limits

    apply_resource_limits(limits)
    resource_types = {
        "cpu": resource.RLIMIT_CPU,
        "open_files": resource.RLIMIT_NOFILE,
    }
    if hasattr(resource, "RLIMIT_AS"):
        resource_types["address_space"] = resource.RLIMIT_AS
    result_queue.put(
        {
            name: resource.getrlimit(resource_type)[0]
            for name, resource_type in resource_types.items()
        }
    )


def _memory_exhausted_pdf_preflight_worker(
    document: bytes,
    limits,
    result_connection,
) -> None:
    repository = _repository_module()

    def raise_memory_error(*args, **kwargs):
        raise MemoryError

    repository.fitz.open = raise_memory_error
    repository._pdf_preflight_worker(document, limits, result_connection)


def _blocking_pdf_preflight_worker(
    document: bytes,
    limits,
    result_connection,
    process_id_path: str,
) -> None:
    del document, limits, result_connection
    Path(process_id_path).write_text(str(os.getpid()), encoding="utf-8")
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    multiprocessing.Event().wait()


def _assert_process_is_gone(process_id_path: Path) -> None:
    process_id = int(process_id_path.read_text(encoding="utf-8"))
    deadline = time.monotonic() + 1
    while time.monotonic() < deadline:
        try:
            os.kill(process_id, 0)
        except ProcessLookupError:
            return
        time.sleep(0.01)
    pytest.fail(f"process {process_id} is still alive")


def test_repository_does_not_expose_an_unisolated_import_api(tmp_path: Path) -> None:
    repository = _repository_module()
    store = repository.ImportRepository(
        database_path=tmp_path / "spend-memory.duckdb",
        data_directory=tmp_path / "data",
    )

    assert not hasattr(store, "import_document")


def test_initial_migration_is_transactional_and_idempotent(tmp_path: Path) -> None:
    repository = _repository_module()
    database_path = tmp_path / "spend-memory.duckdb"

    repository.apply_migrations(database_path)
    repository.apply_migrations(database_path)

    with duckdb.connect(str(database_path), read_only=True) as connection:
        versions = connection.execute(
            "SELECT version FROM storage_migrations ORDER BY version"
        ).fetchall()
        member_constraints = connection.execute(
            """
            SELECT constraint_text
            FROM duckdb_constraints()
            WHERE table_name = 'recurring_candidate_members'
              AND constraint_type = 'FOREIGN KEY'
            ORDER BY constraint_text
            """
        ).fetchall()
        generation_foreign_keys = connection.execute(
            """
            SELECT table_name, constraint_text
            FROM duckdb_constraints()
            WHERE table_name IN ('recurring_candidates', 'recurring_candidate_state')
              AND constraint_type = 'FOREIGN KEY'
              AND constraint_text LIKE '%generation%'
            ORDER BY table_name
            """
        ).fetchall()
        counterparty_constraints = connection.execute(
            """
            SELECT table_name, constraint_type, constraint_column_names, constraint_text
            FROM duckdb_constraints()
            WHERE table_name IN (
                'counterparties',
                'counterparty_aliases',
                'transaction_counterparty_assignments'
            )
              AND constraint_type IN ('PRIMARY KEY', 'UNIQUE', 'FOREIGN KEY')
            """
        ).fetchall()
        counterparty_columns = connection.execute(
            """
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'main'
              AND table_name IN (
                'counterparties',
                'counterparty_aliases',
                'transaction_counterparty_assignments'
            )
              AND (column_name LIKE '%\\_id' ESCAPE '\\' OR column_name LIKE '%\\_at' ESCAPE '\\')
            """
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

    assert versions == [
        ("0001_import_storage",),
        ("0002_raw_amount_normalization",),
        ("0003_enrichment",),
        ("0004_recurring_candidate_members",),
        ("0005_recurring_candidate_generations",),
        ("0006_counterparties",),
        ("0007_demo_imports",),
    ]
    assert {
        "source_documents",
        "import_runs",
        "raw_transactions",
        "import_errors",
        "recurring_candidate_members",
        "recurring_candidate_generations",
        "recurring_candidate_state",
        "counterparties",
        "counterparty_aliases",
        "transaction_counterparty_assignments",
    } <= tables
    assert member_constraints == [
        ("FOREIGN KEY (raw_transaction_id) REFERENCES raw_transactions(raw_transaction_id)",),
        (
            (
                "FOREIGN KEY (recurring_candidate_id) REFERENCES "
                "recurring_candidates(recurring_candidate_id)"
            ),
        ),
    ]
    assert generation_foreign_keys == [
        (
            "recurring_candidate_state",
            (
                "FOREIGN KEY (active_generation_id) REFERENCES "
                "recurring_candidate_generations(generation_id)"
            ),
        ),
        (
            "recurring_candidates",
            (
                "FOREIGN KEY (generation_id) REFERENCES "
                "recurring_candidate_generations(generation_id)"
            ),
        ),
    ]
    primary_key_columns = {
        (table_name, column_name)
        for table_name, constraint_type, columns, _ in counterparty_constraints
        if constraint_type == "PRIMARY KEY"
        for column_name in columns
    }
    assert {
        table_name: tuple(columns)
        for table_name, constraint_type, columns, _ in counterparty_constraints
        if constraint_type == "PRIMARY KEY"
    } == {
        "counterparties": ("counterparty_id",),
        "counterparty_aliases": ("counterparty_alias_id",),
        "transaction_counterparty_assignments": (
            "transaction_counterparty_assignment_id",
        ),
    }
    assert {
        (table_name, column_name): data_type
        for table_name, column_name, data_type in counterparty_columns
        if (table_name, column_name) in primary_key_columns
    } == {
        ("counterparties", "counterparty_id"): "UUID",
        ("counterparty_aliases", "counterparty_alias_id"): "UUID",
        (
            "transaction_counterparty_assignments",
            "transaction_counterparty_assignment_id",
        ): "UUID",
    }
    assert {
        (table_name, column_name): data_type
        for table_name, column_name, data_type in counterparty_columns
        if column_name.endswith("_at")
    } == {
        ("counterparties", "created_at"): "TIMESTAMP WITH TIME ZONE",
        ("counterparty_aliases", "confirmed_at"): "TIMESTAMP WITH TIME ZONE",
        (
            "transaction_counterparty_assignments",
            "confirmed_at",
        ): "TIMESTAMP WITH TIME ZONE",
    }
    assert {
        (table_name, tuple(columns))
        for table_name, constraint_type, columns, _ in counterparty_constraints
        if constraint_type == "UNIQUE"
    } == {
        ("counterparty_aliases", ("normalized_descriptor",)),
        ("transaction_counterparty_assignments", ("raw_transaction_id",)),
    }
    assert {
        constraint_text
        for table_name, constraint_type, _, constraint_text in counterparty_constraints
        if table_name == "counterparty_aliases"
        and constraint_type == "FOREIGN KEY"
    } == {
        "FOREIGN KEY (counterparty_id) REFERENCES counterparties(counterparty_id)",
    }
    assert {
        constraint_text
        for table_name, constraint_type, _, constraint_text in counterparty_constraints
        if table_name == "transaction_counterparty_assignments"
        and constraint_type == "FOREIGN KEY"
    } == {
        "FOREIGN KEY (counterparty_id) REFERENCES counterparties(counterparty_id)",
        "FOREIGN KEY (raw_transaction_id) REFERENCES raw_transactions(raw_transaction_id)",
    }


def test_failed_migration_rolls_back_schema_and_migration_ledger(
    tmp_path: Path,
) -> None:
    repository = _repository_module()
    database_path = tmp_path / "spend-memory.duckdb"
    migration_directory = tmp_path / "migrations"
    migration_directory.mkdir()
    (migration_directory / "0002_create_probe.sql").write_text(
        "CREATE TABLE migration_probe (id INTEGER);",
        encoding="utf-8",
    )
    (migration_directory / "0003_invalid.sql").write_text(
        "CREATE TABLE broken_migration (",
        encoding="utf-8",
    )

    with pytest.raises(duckdb.ParserException):
        repository.apply_migrations(
            database_path,
            migration_directory=migration_directory,
        )

    with duckdb.connect(str(database_path), read_only=True) as connection:
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

    assert "migration_probe" not in tables
    assert "storage_migrations" not in tables


def test_generation_migration_preserves_existing_recurring_lineage(
    tmp_path: Path,
) -> None:
    repository = _repository_module()
    database_path = tmp_path / "spend-memory.duckdb"
    prior_migrations = tmp_path / "prior-migrations"
    prior_migrations.mkdir()
    bundled_migrations = Path(repository.__file__).parent / "migrations"
    for migration_path in sorted(bundled_migrations.glob("000[1-4]_*.sql")):
        (prior_migrations / migration_path.name).write_text(
            migration_path.read_text(encoding="utf-8"), encoding="utf-8"
        )
    repository.apply_migrations(
        database_path, migration_directory=prior_migrations
    )
    with duckdb.connect(str(database_path)) as connection:
        connection.execute(
            """
            INSERT INTO source_documents
            SELECT uuid(), 'generation-upgrade', 'test.csv', 'text/csv', 0,
                   'test.csv', now()
            """
        )
        connection.execute(
            """
            INSERT INTO import_runs (
                run_id, document_id, parser_id, parser_version, is_active
            )
            SELECT uuid(), document_id, 'synthetic', 'v1', true
            FROM source_documents
            """
        )
        connection.execute(
            """
            INSERT INTO raw_transactions (
                raw_transaction_id, import_run_id, source_ordinal, date_text,
                description_text, amount_text, extraction_method,
                extraction_confidence
            )
            SELECT uuid(), run_id, 1, '2026-01-01', 'Legacy plan', '-100',
                   'synthetic', 1
            FROM import_runs
            """
        )
        connection.execute(
            """
            INSERT INTO recurring_candidates
            SELECT uuid(), 'legacy-key', 'synthetic-account', NULL,
                   'legacy plan', 'AED', 'debit', 'monthly', DATE '2026-01-01',
                   DATE '2026-03-01', 100, 100, DATE '2026-04-01',
                   DATE '2026-04-03', 1, '{}', 'candidate', 'v1'
            """
        )
        connection.execute(
            """
            INSERT INTO recurring_candidate_members
            SELECT recurring_candidate_id, raw_transaction_id
            FROM recurring_candidates CROSS JOIN raw_transactions
            """
        )

    repository.apply_migrations(database_path)

    with duckdb.connect(str(database_path), read_only=True) as connection:
        assert connection.execute(
            """
            SELECT c.candidate_key, g.candidate_count, g.member_count,
                   m.raw_transaction_id = t.raw_transaction_id
            FROM recurring_candidate_state s
            JOIN recurring_candidate_generations g
              ON g.generation_id = s.active_generation_id
            JOIN recurring_candidates c USING (generation_id)
            JOIN recurring_candidate_members m USING (recurring_candidate_id)
            JOIN raw_transactions t USING (raw_transaction_id)
            """
        ).fetchone() == ("legacy-key", 1, 1, True)


def test_source_document_identity_is_the_sha256_of_original_bytes(
    tmp_path: Path,
) -> None:
    repository = _repository_module()
    store = repository.ImportRepository(
        database_path=tmp_path / "spend-memory.duckdb",
        data_directory=tmp_path / "data",
    )

    first = store._import_document_for_tests(
        document=CSV_DOCUMENT,
        filename="first-name.csv",
        declared_mime_type="text/csv",
        parser=StubParser(version="1.0"),
    )
    second = store._import_document_for_tests(
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

    first = store._import_document_for_tests(
        document=CSV_DOCUMENT,
        filename="statement.csv",
        declared_mime_type="text/csv",
        parser=parser,
    )
    second = store._import_document_for_tests(
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


@pytest.mark.parametrize("damage", ["missing", "corrupt"])
def test_idempotent_retry_repairs_missing_or_corrupt_original_file(
    tmp_path: Path,
    damage: str,
) -> None:
    repository = _repository_module()
    store = repository.ImportRepository(
        database_path=tmp_path / "spend-memory.duckdb",
        data_directory=tmp_path / "data",
    )
    parser = StubParser()
    first = store._import_document_for_tests(
        document=CSV_DOCUMENT,
        filename="statement.csv",
        declared_mime_type="text/csv",
        parser=parser,
    )
    final_path = store.data_directory / f"{sha256(CSV_DOCUMENT).hexdigest()}.csv"
    if damage == "missing":
        final_path.unlink()
    else:
        final_path.write_bytes(b"corrupt original")

    repeated = store._import_document_for_tests(
        document=CSV_DOCUMENT,
        filename="statement.csv",
        declared_mime_type="text/csv",
        parser=parser,
    )

    assert repeated.document_id == first.document_id
    assert repeated.run_id == first.run_id
    assert repeated.was_already_imported is True
    assert parser.parse_calls == 1
    assert final_path.read_bytes() == CSV_DOCUMENT


def test_new_parser_version_repairs_corrupt_original_file(
    tmp_path: Path,
) -> None:
    repository = _repository_module()
    store = repository.ImportRepository(
        database_path=tmp_path / "spend-memory.duckdb",
        data_directory=tmp_path / "data",
    )
    store._import_document_for_tests(
        document=CSV_DOCUMENT,
        filename="statement.csv",
        declared_mime_type="text/csv",
        parser=StubParser(version="1.0"),
    )
    final_path = store.data_directory / f"{sha256(CSV_DOCUMENT).hexdigest()}.csv"
    final_path.write_bytes(b"corrupt original")

    result = store._import_document_for_tests(
        document=CSV_DOCUMENT,
        filename="statement.csv",
        declared_mime_type="text/csv",
        parser=StubParser(version="2.0"),
    )

    assert result.was_already_imported is False
    assert final_path.read_bytes() == CSV_DOCUMENT


def test_concurrent_preparsed_imports_share_one_import_run(tmp_path: Path) -> None:
    repository = _repository_module()
    store = repository.ImportRepository(
        database_path=tmp_path / "spend-memory.duckdb",
        data_directory=tmp_path / "data",
    )
    parser = ConcurrentParser()

    def import_statement():
        return store._import_document_for_tests(
            document=CSV_DOCUMENT,
            filename="statement.csv",
            declared_mime_type="text/csv",
            parser=parser,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        first_future = executor.submit(import_statement)
        assert parser.first_parse_entered.wait(timeout=5)
        second_future = executor.submit(import_statement)
        parser.second_parse_entered.wait(timeout=1)
        parser.release_first_parse.set()
        results = [first_future.result(), second_future.result()]

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

    assert parser.parse_calls == 2
    assert results[0].document_id == results[1].document_id
    assert results[0].run_id == results[1].run_id
    assert sorted(result.was_already_imported for result in results) == [False, True]
    assert counts == (1, 1, 1, 0)


def test_independent_preparsed_imports_share_one_import_run(
    tmp_path: Path,
) -> None:
    repository = _repository_module()
    database_path = tmp_path / "spend-memory.duckdb"
    data_directory = tmp_path / "data"
    repository.ImportRepository(
        database_path=database_path,
        data_directory=data_directory,
    )
    process_context = multiprocessing.get_context("spawn")
    ready_queue = process_context.Queue()
    result_queue = process_context.Queue()
    start_import = process_context.Event()
    both_parsers_entered = process_context.Event()
    parse_count = process_context.Value("i", 0)
    worker_arguments = (
        str(database_path),
        str(data_directory),
        ready_queue,
        start_import,
        parse_count,
        both_parsers_entered,
        result_queue,
    )
    workers = [
        process_context.Process(
            target=_run_independent_process_import,
            args=worker_arguments,
        )
        for _ in range(2)
    ]

    try:
        workers[0].start()
        assert ready_queue.get(timeout=10) is True
        workers[1].start()
        assert ready_queue.get(timeout=10) is True
        start_import.set()
        results = [result_queue.get(timeout=15) for _ in workers]
        for worker in workers:
            worker.join(timeout=10)
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
            worker.join(timeout=10)

    assert parse_count.value == 2
    assert [result[0] for result in results] == ["ok", "ok"]
    assert results[0][1:3] == results[1][1:3]
    assert sorted(result[3] for result in results) == [False, True]
    assert not (data_directory / ".locks").exists()


def test_independent_processes_coordinate_duckdb_writes_for_distinct_documents(
    tmp_path: Path,
) -> None:
    repository = _repository_module()
    database_path = tmp_path / "spend-memory.duckdb"
    data_directory = tmp_path / "data"
    repository.ImportRepository(
        database_path=database_path,
        data_directory=data_directory,
    )
    process_context = multiprocessing.get_context("spawn")
    ready_queue = process_context.Queue()
    result_queue = process_context.Queue()
    start_import = process_context.Event()
    both_parsers_entered = process_context.Event()
    parse_count = process_context.Value("i", 0)
    documents = (
        CSV_DOCUMENT,
        CSV_DOCUMENT.replace(b"-1200", b"-1300"),
    )
    workers = [
        process_context.Process(
            target=_run_distinct_document_process_import,
            args=(
                str(database_path),
                str(data_directory),
                document,
                ready_queue,
                start_import,
                parse_count,
                both_parsers_entered,
                result_queue,
            ),
        )
        for document in documents
    ]

    try:
        for worker in workers:
            worker.start()
            assert ready_queue.get(timeout=10) is True
        start_import.set()
        results = [result_queue.get(timeout=15) for _ in workers]
        for worker in workers:
            worker.join(timeout=10)
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
            worker.join(timeout=10)

    with duckdb.connect(str(database_path), read_only=True) as connection:
        counts = connection.execute(
            """
            SELECT
                (SELECT count(*) FROM source_documents),
                (SELECT count(*) FROM import_runs),
                (SELECT count(*) FROM raw_transactions),
                (SELECT count(*) FROM import_errors)
            """
        ).fetchone()

    assert [result[0] for result in results] == ["ok", "ok"]
    assert counts == (2, 2, 2, 0)


def test_database_lock_uses_canonical_path_across_symlink_aliases(
    tmp_path: Path,
) -> None:
    repository = _repository_module()
    database_path = tmp_path / "spend-memory.duckdb"
    database_alias = tmp_path / "database-alias.duckdb"
    data_directory = tmp_path / "data"
    repository.ImportRepository(
        database_path=database_path,
        data_directory=data_directory,
    )
    database_alias.symlink_to(database_path)
    process_context = multiprocessing.get_context("spawn")
    ready_queue = process_context.Queue()
    result_queue = process_context.Queue()
    start_import = process_context.Event()
    both_parsers_entered = process_context.Event()
    parse_count = process_context.Value("i", 0)
    workers = [
        process_context.Process(
            target=_run_distinct_document_process_import,
            args=(
                str(worker_database_path),
                str(data_directory),
                document,
                ready_queue,
                start_import,
                parse_count,
                both_parsers_entered,
                result_queue,
            ),
        )
        for worker_database_path, document in (
            (database_path, CSV_DOCUMENT),
            (database_alias, CSV_DOCUMENT.replace(b"-1200", b"-1300")),
        )
    ]

    try:
        for worker in workers:
            worker.start()
            assert ready_queue.get(timeout=10) is True
        start_import.set()
        results = [result_queue.get(timeout=15) for _ in workers]
        for worker in workers:
            worker.join(timeout=10)
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
            worker.join(timeout=10)

    with duckdb.connect(str(database_path), read_only=True) as connection:
        document_count = connection.execute(
            "SELECT count(*) FROM source_documents"
        ).fetchone()

    assert [result[0] for result in results] == ["ok", "ok"]
    assert document_count == (2,)


def test_concurrent_parser_versions_cannot_remove_a_successful_source_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _repository_module()
    database_path = tmp_path / "spend-memory.duckdb"
    data_directory = tmp_path / "data"
    failing_store = repository.ImportRepository(
        database_path=database_path,
        data_directory=data_directory,
    )
    successful_store = repository.ImportRepository(
        database_path=database_path,
        data_directory=data_directory,
    )
    failed_version = StubParser(version="1.0")
    successful_version = SignalingParser(version="2.0")
    first_final_file_moved = Event()
    release_failed_move = Event()
    real_replace = repository.os.replace
    replace_calls = 0
    replace_calls_lock = Lock()

    def pause_first_move_then_fail(source: Path, destination: Path) -> None:
        nonlocal replace_calls
        with replace_calls_lock:
            replace_calls += 1
            call_number = replace_calls
        real_replace(source, destination)
        if call_number == 1:
            first_final_file_moved.set()
            if not release_failed_move.wait(timeout=10):
                raise RuntimeError("concurrency test did not release file move")
            raise OSError("SENSITIVE-AFTER-FINAL-MOVE")

    monkeypatch.setattr(repository.os, "replace", pause_first_move_then_fail)

    def import_failed_version():
        with pytest.raises(repository.ImportRepositoryError) as caught:
            failing_store._import_document_for_tests(
                document=CSV_DOCUMENT,
                filename="statement.csv",
                declared_mime_type="text/csv",
                parser=failed_version,
            )
        return caught.value.code

    def import_successful_version():
        return successful_store._import_document_for_tests(
            document=CSV_DOCUMENT,
            filename="statement.csv",
            declared_mime_type="text/csv",
            parser=successful_version,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        failed_future = executor.submit(import_failed_version)
        assert first_final_file_moved.wait(timeout=5)
        successful_future = executor.submit(import_successful_version)
        entered_while_failed_import_owned_file = (
            successful_version.parse_entered.wait(timeout=1)
        )
        release_failed_move.set()
        failed_code = failed_future.result(timeout=10)
        successful_result = successful_future.result(timeout=10)

    final_path = data_directory / f"{sha256(CSV_DOCUMENT).hexdigest()}.csv"
    assert entered_while_failed_import_owned_file is False
    assert failed_code == "storage_failed"
    assert successful_result.was_already_imported is False
    assert final_path.read_bytes() == CSV_DOCUMENT
    assert not (data_directory / ".locks").exists()


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

    first = store._import_document_for_tests(
        document=CSV_DOCUMENT,
        filename="statement.csv",
        declared_mime_type="text/csv",
        parser=version_one,
    )
    second = store._import_document_for_tests(
        document=CSV_DOCUMENT,
        filename="statement.csv",
        declared_mime_type="text/csv",
        parser=version_two,
    )
    repeated_old_version = store._import_document_for_tests(
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

    result = store._import_document_for_tests(
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


def test_raw_amount_and_ocr_normalization_are_stored_separately(
    tmp_path: Path,
) -> None:
    repository = _repository_module()
    transaction = StubParser()._transactions[0]
    ocr_transaction = ParsedRawTransaction(
        date_text=transaction.date_text,
        description_text=transaction.description_text,
        amount_text="-I2O0",
        currency_text=transaction.currency_text,
        source_page=1,
        source_row=1,
        source_text="2026-01-01\nSynthetic test purchase\n-I2O0",
        extraction_method="ocr:tesseract",
        normalized_amount_text="-1200",
    )
    store = repository.ImportRepository(
        database_path=tmp_path / "spend-memory.duckdb",
        data_directory=tmp_path / "data",
    )

    result = store._import_document_for_tests(
        document=CSV_DOCUMENT,
        filename="statement.csv",
        declared_mime_type="text/csv",
        parser=StubParser(transactions=[ocr_transaction]),
    )

    with duckdb.connect(str(store.database_path), read_only=True) as connection:
        stored = connection.execute(
            """
            SELECT amount_text, normalized_amount_text
            FROM raw_transactions
            WHERE import_run_id = ?
            """,
            [result.run_id],
        ).fetchone()

    assert stored == ("-I2O0", "-1200")


def test_parser_failure_is_recorded_without_partial_import_data(
    tmp_path: Path,
) -> None:
    repository = _repository_module()
    store = repository.ImportRepository(
        database_path=tmp_path / "spend-memory.duckdb",
        data_directory=tmp_path / "data",
    )

    with pytest.raises(repository.ImportRepositoryError) as caught:
        store._import_document_for_tests(
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
    assert list(store.data_directory.iterdir()) == []


def test_failed_reprocessing_does_not_replace_the_active_run(
    tmp_path: Path,
) -> None:
    repository = _repository_module()
    store = repository.ImportRepository(
        database_path=tmp_path / "spend-memory.duckdb",
        data_directory=tmp_path / "data",
    )
    active = store._import_document_for_tests(
        document=CSV_DOCUMENT,
        filename="statement.csv",
        declared_mime_type="text/csv",
        parser=StubParser(version="1.0"),
    )

    with pytest.raises(repository.ImportRepositoryError):
        store._import_document_for_tests(
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
        store._import_document_for_tests(
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


def test_failure_after_final_file_move_removes_rows_and_source_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _repository_module()
    store = repository.ImportRepository(
        database_path=tmp_path / "spend-memory.duckdb",
        data_directory=tmp_path / "data",
    )
    final_path = (
        store.data_directory / f"{sha256(CSV_DOCUMENT).hexdigest()}.csv"
    )
    real_replace = repository.os.replace
    moved_paths: list[Path] = []

    def move_then_fail(source: Path, destination: Path) -> None:
        real_replace(source, destination)
        moved_paths.append(Path(destination))
        raise OSError("SENSITIVE-AFTER-FINAL-MOVE")

    monkeypatch.setattr(repository.os, "replace", move_then_fail)

    with pytest.raises(repository.ImportRepositoryError) as caught:
        store._import_document_for_tests(
            document=CSV_DOCUMENT,
            filename="statement.csv",
            declared_mime_type="text/csv",
            parser=StubParser(),
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
        stored_error = connection.execute(
            "SELECT error_type, error_message FROM import_errors"
        ).fetchone()

    assert moved_paths == [final_path]
    assert caught.value.code == "storage_failed"
    assert str(caught.value) == "storage_failed"
    assert caught.value.__cause__ is None
    assert "SENSITIVE-AFTER-FINAL-MOVE" not in str(caught.value)
    assert counts == (0, 0, 0, 1)
    assert stored_error == ("storage_failed", "storage_failed")
    assert not final_path.exists()
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
        store._import_document_for_tests(
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
        store._import_document_for_tests(
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
        store._import_document_for_tests(
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


def test_document_workers_apply_effective_resource_limits() -> None:
    from spend_memory.ingestion.resource_limits import ResourceLimits

    process_context = multiprocessing.get_context("spawn")
    result_queue = process_context.Queue()
    worker = process_context.Process(
        target=_report_effective_resource_limits,
        args=(
            ResourceLimits(
                cpu_seconds=25,
                address_space_bytes=1_500 * 1024 * 1024,
                max_open_files=64,
            ),
            result_queue,
        ),
    )

    worker.start()
    worker.join(timeout=5)

    try:
        assert worker.exitcode == 0
        effective_limits = result_queue.get(timeout=1)
        assert effective_limits["cpu"] <= 25
        assert effective_limits["open_files"] <= 64
        if sys.platform.startswith("linux"):
            assert effective_limits["address_space"] <= 1_500 * 1024 * 1024
    finally:
        result_queue.close()
        result_queue.join_thread()
        worker.close()


def test_pdf_preflight_uses_the_parser_worker_resource_budget() -> None:
    repository = _repository_module()

    resource_limits = repository.ImportLimits(
        parser_cpu_limit_seconds=7,
        parser_address_space_bytes=256 * 1024 * 1024,
        parser_max_open_files=12,
    ).pdf_preflight_resource_limits()

    assert resource_limits.cpu_seconds == 7
    assert resource_limits.address_space_bytes == 256 * 1024 * 1024
    assert resource_limits.max_open_files == 12


def test_pdf_preflight_maps_memory_exhaustion_to_a_safe_resource_error() -> None:
    repository = _repository_module()
    process_context = multiprocessing.get_context("spawn")
    receive_result, send_result = process_context.Pipe(duplex=False)
    document = _pdf_with_pages(1)
    original_cpu_limit = resource.getrlimit(resource.RLIMIT_CPU)
    worker = process_context.Process(
        target=_memory_exhausted_pdf_preflight_worker,
        args=(document, repository.DEFAULT_IMPORT_LIMITS, send_result),
    )

    worker.start()
    send_result.close()
    worker.join(timeout=5)
    try:
        assert worker.exitcode == 0
        assert receive_result.recv() == "resource_limit"
        assert resource.getrlimit(resource.RLIMIT_CPU) == original_cpu_limit
    finally:
        receive_result.close()
        if worker.is_alive():
            worker.kill()
            worker.join(timeout=0.1)
        worker.close()


def test_pdf_preflight_timeout_does_not_wait_for_an_unresponsive_worker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _repository_module()
    worker_id_path = tmp_path / "pdf-preflight.pid"
    process_context = multiprocessing.get_context("spawn")

    class _BlockingPreflightContext:
        def Pipe(self, *args, **kwargs):
            return process_context.Pipe(*args, **kwargs)

        def Process(self, *, target, args):
            del target
            return process_context.Process(
                target=_blocking_pdf_preflight_worker,
                args=(*args, str(worker_id_path)),
            )

    monkeypatch.setattr(
        repository.multiprocessing,
        "get_context",
        lambda name: _BlockingPreflightContext(),
    )
    store = repository.ImportRepository(
        database_path=tmp_path / "spend-memory.duckdb",
        data_directory=tmp_path / "data",
        limits=repository.ImportLimits(pdf_preflight_timeout_seconds=1),
    )

    started_at = time.monotonic()
    with pytest.raises(repository.ImportRepositoryError) as caught:
        store._validate_pdf(_pdf_with_pages(1))

    assert caught.value.code == "pdf_preflight_timeout"
    assert time.monotonic() - started_at < 1.5
    _assert_process_is_gone(worker_id_path)


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
        store._import_document_for_tests(
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
