from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import duckdb
import pytest
from spend_memory.enrichment.repository import EnrichmentRepository


def test_enrichment_migration_is_idempotent_and_keeps_annotations_local(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "spend-memory.duckdb"
    EnrichmentRepository(database_path)
    EnrichmentRepository(database_path)

    with duckdb.connect(str(database_path), read_only=True) as connection:
        tables = {row[0] for row in connection.execute("show tables").fetchall()}
        assert {
            "merchants",
            "merchant_aliases",
            "categories",
            "transaction_merchant_annotations",
        } <= tables
        assert "amount_minor" not in {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info('transaction_merchant_annotations')"
            ).fetchall()
        }


def test_confirmed_alias_and_transaction_override_keep_lineage(tmp_path: Path) -> None:
    repository = EnrichmentRepository(tmp_path / "spend-memory.duckdb")
    merchant = repository.create_merchant("MetroMart")
    repository.confirm_alias("METRO MART", merchant.merchant_id)
    category = repository.create_category("Groceries")
    transaction_id = uuid4()
    document_id = uuid4()
    run_id = uuid4()
    with duckdb.connect(str(repository.database_path)) as connection:
        connection.execute(
            """
            INSERT INTO source_documents (
                document_id, sha256_hex, original_filename, mime_type, byte_size,
                storage_filename
            ) VALUES (?, 'synthetic', 'test.csv', 'text/csv', 0, 'test.csv')
            """,
            [document_id],
        )
        connection.execute(
            """
            INSERT INTO import_runs (run_id, document_id, parser_id, parser_version)
            VALUES (?, ?, 'synthetic', 'v1')
            """,
            [run_id, document_id],
        )
        connection.execute(
            """
            INSERT INTO raw_transactions (
                raw_transaction_id, import_run_id, source_ordinal, date_text,
                description_text, amount_text, extraction_method, extraction_confidence
            ) VALUES (?, ?, 1, '2026-01-01', 'Metro Mart', '-100', 'synthetic', 1)
            """,
            [transaction_id, run_id],
        )
    repository.set_transaction_category_override(transaction_id, category.category_id)

    assert repository.find_confirmed_alias("metro mart").merchant_id == merchant.merchant_id
    assert repository.find_transaction_category_override(transaction_id) == category


def test_category_label_cannot_be_blank(tmp_path: Path) -> None:
    repository = EnrichmentRepository(tmp_path / "spend-memory.duckdb")

    with pytest.raises(ValueError, match="category_label_required"):
        repository.create_category("   ")
