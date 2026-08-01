from __future__ import annotations

import os
import subprocess
from pathlib import Path

import duckdb
from spend_memory.ingestion.parsers.canonical_csv import CanonicalCsvParser
from spend_memory.ingestion.parsers.synthetic_pdf_a import SyntheticAedTabularPdfParser
from spend_memory.ingestion.parsers.synthetic_pdf_b import SyntheticPkrCompactPdfParser
from spend_memory.ingestion.registry import ParserRegistry
from spend_memory.ingestion.service import IngestionService
from spend_memory.storage.repository import ImportRepository

from sample_data.generator.generate import generate_dataset


def _build_fixture_database(tmp_path: Path) -> Path:
    dataset = generate_dataset(tmp_path / "sample_data")
    database_path = tmp_path / "spend-memory.duckdb"
    repository = ImportRepository(
        database_path=database_path,
        data_directory=tmp_path / "documents",
    )
    service = IngestionService(
        repository=repository,
        parser_registry=ParserRegistry(
            [
                CanonicalCsvParser(),
                SyntheticAedTabularPdfParser(),
                SyntheticPkrCompactPdfParser(),
            ]
        ),
    )
    for source_path in sorted((dataset.csv_path.parent).glob("*.pdf")):
        if source_path.name != "aed_statement_image_only.pdf":
            service.import_document(
                document=source_path.read_bytes(),
                filename=source_path.name,
                declared_mime_type="application/pdf",
            )
    service.import_document(
        document=dataset.csv_path.read_bytes(),
        filename=dataset.csv_path.name,
        declared_mime_type="text/csv",
    )
    return database_path


def _dbt_build(database_path: Path, select: str | None = None) -> None:
    environment = {**os.environ, "SPEND_MEMORY_DUCKDB_PATH": str(database_path)}
    command = [
        "uv",
        "run",
        "dbt",
        "build",
        "--project-dir",
        "analytics",
        "--profiles-dir",
        "analytics",
        "--indirect-selection",
        "cautious",
    ]
    if select:
        command.extend(["--select", *(f"+{model}" for model in select.split())])
    subprocess.run(command, check=True, env=environment, text=True)


def test_dbt_builds_staging_models_from_active_imports(tmp_path: Path) -> None:
    database_path = _build_fixture_database(tmp_path)
    _dbt_build(database_path, "stg_transactions stg_transaction_rejections")
    with duckdb.connect(str(database_path), read_only=True) as connection:
        accepted = connection.execute("select count(*) from analytics.stg_transactions").fetchone()[0]
        rejected = connection.execute("select count(*) from analytics.stg_transaction_rejections").fetchone()[0]
        currencies = connection.execute("select distinct currency from analytics.stg_transactions order by 1").fetchall()
    assert accepted == 864
    assert rejected == 0
    assert currencies == [("AED",), ("PKR",)]


def test_dbt_marks_matching_synthetic_imports_reconciled(tmp_path: Path) -> None:
    database_path = _build_fixture_database(tmp_path)
    _dbt_build(database_path, "int_import_reconciliation")
    with duckdb.connect(str(database_path), read_only=True) as connection:
        statuses = connection.execute(
            "select reconciliation_status, count(*) from analytics.int_import_reconciliation group by 1 order by 1"
        ).fetchall()
    assert statuses == [("reconciled", 3)]


def test_duplicate_candidates_keep_every_transaction(tmp_path: Path) -> None:
    database_path = _build_fixture_database(tmp_path)
    _dbt_build(database_path, "int_duplicate_candidates")
    with duckdb.connect(str(database_path), read_only=True) as connection:
        staged = connection.execute("select count(*) from analytics.stg_transactions").fetchone()[0]
        candidates = connection.execute("select count(*) from analytics.int_duplicate_candidates").fetchone()[0]
    assert staged == 864
    assert candidates >= 2


def test_trusted_marts_match_the_canonical_ledger(tmp_path: Path) -> None:
    database_path = _build_fixture_database(tmp_path)
    _dbt_build(database_path, "mart_transactions mart_monthly_summary mart_period_comparisons")
    with duckdb.connect(str(database_path), read_only=True) as connection:
        transaction_count = connection.execute("select count(*) from analytics.mart_transactions").fetchone()[0]
        total = connection.execute("select sum(net_amount_minor) from analytics.mart_transactions").fetchone()[0]
        currencies = connection.execute(
            "select distinct currency from analytics.mart_monthly_summary order by 1"
        ).fetchall()
    assert transaction_count == 864
    assert total == -114355263
    assert currencies == [("AED",), ("PKR",)]


def test_unreconciled_import_is_excluded_from_trusted_marts(tmp_path: Path) -> None:
    database_path = _build_fixture_database(tmp_path)
    with duckdb.connect(str(database_path)) as connection:
        connection.execute("update raw_transactions set amount_text = '-999999999' where source_ordinal = 1")
    _dbt_build(database_path, "mart_transactions")
    with duckdb.connect(str(database_path), read_only=True) as connection:
        statuses = connection.execute(
            "select distinct reconciliation_status from analytics.int_import_reconciliation"
        ).fetchall()
        count = connection.execute("select count(*) from analytics.mart_transactions").fetchone()[0]
    assert ("unreconciled",) in statuses
    assert count < 864
