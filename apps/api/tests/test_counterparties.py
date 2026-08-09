from __future__ import annotations

from datetime import date
from pathlib import Path
from uuid import UUID, uuid4

import duckdb
import pytest
from spend_memory.enrichment.models import TrustedTransaction
from spend_memory.enrichment.repository import EnrichmentRepository


def _add_raw_transaction(repository: EnrichmentRepository) -> UUID:
    transaction_id = uuid4()
    document_id = uuid4()
    run_id = uuid4()
    with duckdb.connect(str(repository.database_path)) as connection:
        connection.execute(
            """
            INSERT INTO source_documents (
                document_id, sha256_hex, original_filename, mime_type, byte_size,
                storage_filename
            ) VALUES (?, ?, 'synthetic.csv', 'text/csv', 0, 'synthetic.csv')
            """,
            [document_id, str(document_id)],
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
            ) VALUES (?, ?, 1, '2026-01-01', 'Rina', '-100', 'synthetic', 1)
            """,
            [transaction_id, run_id],
        )
    return transaction_id


def _add_trusted_mart(repository: EnrichmentRepository, transaction_id: UUID) -> None:
    with duckdb.connect(str(repository.database_path)) as connection:
        connection.execute("CREATE SCHEMA analytics")
        connection.execute(
            """
            CREATE TABLE analytics.mart_transactions (
                raw_transaction_id UUID,
                account_identity VARCHAR,
                transaction_date DATE,
                description VARCHAR,
                currency VARCHAR,
                amount_minor BIGINT,
                direction VARCHAR
            )
            """
        )
        connection.execute(
            """
            INSERT INTO analytics.mart_transactions VALUES
            (?, 'synthetic', '2026-01-01', 'Rina', 'AED', 100, 'debit')
            """,
            [transaction_id],
        )


def test_counterparty_migration_is_additive_and_idempotent(tmp_path: Path) -> None:
    database_path = tmp_path / "spend-memory.duckdb"
    EnrichmentRepository(database_path)
    EnrichmentRepository(database_path)

    with duckdb.connect(str(database_path), read_only=True) as connection:
        tables = {row[0] for row in connection.execute("SHOW TABLES").fetchall()}
        assert {
            "counterparties",
            "counterparty_aliases",
            "transaction_counterparty_assignments",
        } <= tables
        assert "amount_minor" not in {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info('transaction_counterparty_assignments')"
            ).fetchall()
        }


def test_counterparty_aliases_and_assignments_are_confirmed_local_annotations(
    tmp_path: Path,
) -> None:
    repository = EnrichmentRepository(tmp_path / "spend-memory.duckdb")
    transaction_id = _add_raw_transaction(repository)
    _add_trusted_mart(repository, transaction_id)
    rina = repository.create_counterparty("Rina")
    family = repository.create_counterparty("Family")

    repository.confirm_counterparty_alias("RINA   A.", rina.counterparty_id)
    repository.confirm_counterparty_alias("rina a.", family.counterparty_id)
    repository.assign_counterparty_transactions(rina.counterparty_id, [transaction_id])
    repository.assign_counterparty_transactions(family.counterparty_id, [transaction_id])

    assert repository.find_counterparty("rina a.") == family
    assert repository.list_counterparty_transactions(family.counterparty_id) == [
        TrustedTransaction(
            transaction_id,
            "synthetic",
            date(2026, 1, 1),
            "Rina",
            "rina",
            "AED",
            100,
            "debit",
        )
    ]
    with duckdb.connect(str(repository.database_path), read_only=True) as connection:
        assignments = connection.execute(
            "SELECT raw_transaction_id, counterparty_id FROM transaction_counterparty_assignments"
        ).fetchall()
    assert assignments == [(transaction_id, family.counterparty_id)]


def test_counterparty_assignment_requires_a_trusted_mart_transaction(
    tmp_path: Path,
) -> None:
    repository = EnrichmentRepository(tmp_path / "spend-memory.duckdb")
    counterparty = repository.create_counterparty("Rina")
    _add_trusted_mart(repository, uuid4())

    with pytest.raises(ValueError, match="trusted_transaction_required"):
        repository.assign_counterparty_transactions(counterparty.counterparty_id, [uuid4()])
