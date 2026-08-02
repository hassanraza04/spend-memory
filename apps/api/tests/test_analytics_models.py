from __future__ import annotations

import os
import subprocess
from pathlib import Path

import duckdb
import pytest
from spend_memory.enrichment.models import Merchant, MerchantMatch
from spend_memory.enrichment.repository import EnrichmentRepository
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


def _trusted_transaction_id(database_path: Path, description: str):
    with duckdb.connect(str(database_path), read_only=True) as connection:
        return connection.execute(
            "select raw_transaction_id from raw_transactions where description_text = ?",
            [description],
        ).fetchone()[0]


def _confirmed_match(merchant: Merchant) -> MerchantMatch:
    return MerchantMatch(
        merchant.merchant_id,
        merchant.merchant_name,
        "confirmed",
        1.0,
        "confirmed_alias",
        {},
    )


def _suggested_match(merchant: Merchant) -> MerchantMatch:
    return MerchantMatch(
        merchant.merchant_id,
        merchant.merchant_name,
        "suggested",
        0.9,
        "char_ngram_tfidf",
        {},
    )


def test_mart_transactions_exposes_only_confirmed_merchant_and_category(
    tmp_path: Path,
) -> None:
    database_path = _build_fixture_database(tmp_path)
    enrichment = EnrichmentRepository(database_path)
    merchant = enrichment.create_merchant("MetroMart")
    groceries = enrichment.create_category("Groceries")
    enrichment.assign_merchant_category(merchant.merchant_id, groceries.category_id)
    transaction_id = _trusted_transaction_id(database_path, "METRO MART")
    enrichment.save_merchant_annotation(transaction_id, _confirmed_match(merchant))
    suggested_id = _trusted_transaction_id(database_path, "METRO-MART")
    enrichment.save_merchant_annotation(suggested_id, _suggested_match(merchant))

    _dbt_build(
        database_path,
        "mart_transactions mart_merchants mart_categories mart_category_summary",
    )

    with duckdb.connect(str(database_path), read_only=True) as connection:
        rows = connection.execute(
            """
            select raw_transaction_id, merchant_id, category_id
            from analytics.mart_transactions
            where raw_transaction_id in (?, ?)
            """,
            [transaction_id, suggested_id],
        ).fetchall()
        category_labels = connection.execute(
            """
            with transaction_context as (
              select account_identity, currency
              from analytics.mart_transactions
              where raw_transaction_id = ?
            )
            select summary.category_id, summary.category_label
            from analytics.mart_category_summary as summary
            join transaction_context using (account_identity, currency)
            where summary.category_id = ? or summary.category_id is null
            """,
            [suggested_id, groceries.category_id],
        ).fetchall()
    assert set(rows) == {
        (transaction_id, merchant.merchant_id, groceries.category_id),
        (suggested_id, None, None),
    }
    assert (groceries.category_id, "Groceries") in category_labels
    assert (None, "uncategorized") in category_labels


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


@pytest.mark.parametrize(
    "amount_text",
    ["9223372036854775808", "-9223372036854775808"],
    ids=["oversized-positive", "minimum-negative"],
)
def test_dbt_quarantines_amounts_that_cannot_be_canonical_money(
    tmp_path: Path, amount_text: str
) -> None:
    database_path = _build_fixture_database(tmp_path)
    with duckdb.connect(str(database_path)) as connection:
        raw_transaction_id = connection.execute(
            """
            update raw_transactions
            set amount_text = ?
            where raw_transaction_id = (
              select raw_transaction_id from raw_transactions order by raw_transaction_id limit 1
            )
            returning raw_transaction_id
            """,
            [amount_text],
        ).fetchone()[0]

    _dbt_build(database_path, "stg_transaction_rejections")

    with duckdb.connect(str(database_path), read_only=True) as connection:
        rejection = connection.execute(
            """
            select amount_text, rejection_reason
            from analytics.stg_transaction_rejections
            where raw_transaction_id = ?
            """,
            [raw_transaction_id],
        ).fetchone()
    assert rejection == (amount_text, "invalid_amount")


def test_dbt_rejects_missing_currency_as_unsupported(tmp_path: Path) -> None:
    database_path = _build_fixture_database(tmp_path)
    with duckdb.connect(str(database_path)) as connection:
        raw_transaction_id = connection.execute(
            """
            update raw_transactions
            set currency_text = null
            where raw_transaction_id = (
              select raw_transaction_id from raw_transactions order by raw_transaction_id limit 1
            )
            returning raw_transaction_id
            """
        ).fetchone()[0]

    _dbt_build(database_path, "stg_transaction_rejections")

    with duckdb.connect(str(database_path), read_only=True) as connection:
        rejection_reason = connection.execute(
            """
            select rejection_reason
            from analytics.stg_transaction_rejections
            where raw_transaction_id = ?
            """,
            [raw_transaction_id],
        ).fetchone()[0]
    assert rejection_reason == "unsupported_currency"


def test_dbt_marks_matching_synthetic_imports_reconciled(tmp_path: Path) -> None:
    database_path = _build_fixture_database(tmp_path)
    _dbt_build(database_path, "int_import_reconciliation")
    with duckdb.connect(str(database_path), read_only=True) as connection:
        statuses = connection.execute(
            "select reconciliation_status, count(*) from analytics.int_import_reconciliation group by 1 order by 1"
        ).fetchall()
    assert statuses == [("reconciled", 3)]


def test_balance_evidence_never_mixes_currencies_for_one_account(
    tmp_path: Path,
) -> None:
    database_path = _build_fixture_database(tmp_path)
    with duckdb.connect(str(database_path)) as connection:
        import_run_id = connection.execute(
            """
            select run.run_id
            from import_runs as run
            join source_documents as document on run.document_id = document.document_id
            where document.original_filename = 'aed_january_2026.csv'
            """
        ).fetchone()[0]
        connection.execute(
            """
            update raw_transactions
            set
              date_text = case source_ordinal
                when 1 then '1900-01-01'
                when 2 then '1900-01-02'
                when 3 then '1900-01-03'
                when 4 then '1900-01-04'
              end,
              amount_text = case when source_ordinal in (1, 3) then '-100' else '-200' end,
              currency_text = case when source_ordinal in (1, 3) then 'AED' else 'PKR' end,
              raw_balance_text = case source_ordinal
                when 1 then '1000'
                when 2 then '5000'
                when 3 then '900'
                when 4 then '4800'
              end
            where import_run_id = ? and source_ordinal between 1 and 4
            """,
            [import_run_id],
        )

    _dbt_build(database_path, "int_import_reconciliation")

    with duckdb.connect(str(database_path), read_only=True) as connection:
        checks = connection.execute(
            """
            select currency, balance_check_status
            from analytics.int_running_balance_checks
            where import_run_id = ? and source_ordinal between 1 and 4
            order by source_ordinal
            """,
            [import_run_id],
        ).fetchall()
        failed_evidence = connection.execute(
            """
            select currency, has_failed_balance_check
            from analytics.int_import_reconciliation
            where import_run_id = ?
            order by currency
            """,
            [import_run_id],
        ).fetchall()
    assert checks == [
        ("AED", "not_available"),
        ("PKR", "not_available"),
        ("AED", "pass"),
        ("PKR", "pass"),
    ]
    assert failed_evidence == [("AED", False), ("PKR", False)]


def test_dbt_keeps_unavailable_evidence_for_an_empty_active_import(
    tmp_path: Path,
) -> None:
    database_path = _build_fixture_database(tmp_path)
    with duckdb.connect(str(database_path)) as connection:
        document_id = connection.execute(
            """
            insert into source_documents (
              document_id, sha256_hex, original_filename, mime_type, byte_size, storage_filename
            )
            values (uuid(), repeat('0', 64), 'empty.csv', 'text/csv', 0, 'empty.csv')
            returning document_id
            """
        ).fetchone()[0]
        import_run_id = connection.execute(
            """
            insert into import_runs (run_id, document_id, parser_id, parser_version, is_active)
            values (uuid(), ?, 'canonical-csv', 'empty-fixture', true)
            returning run_id
            """,
            [document_id],
        ).fetchone()[0]

    _dbt_build(database_path, "int_import_reconciliation")

    with duckdb.connect(str(database_path), read_only=True) as connection:
        evidence = connection.execute(
            """
            select
              original_filename,
              account_identity,
              currency,
              net_amount_minor,
              expected_net_amount_minor,
              has_failed_balance_check,
              reconciliation_status
            from analytics.int_import_reconciliation
            where import_run_id = ?
            """,
            [import_run_id],
        ).fetchone()
    assert evidence == ("empty.csv", None, None, 0, None, False, "not_available")


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
