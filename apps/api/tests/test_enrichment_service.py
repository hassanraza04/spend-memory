from __future__ import annotations

from pathlib import Path

import duckdb
import pytest
from spend_memory.enrichment.repository import EnrichmentRepository
from spend_memory.enrichment.service import EnrichmentService

from apps.api.tests.test_analytics_models import _build_fixture_database, _dbt_build


def test_refresh_reads_only_reconciled_mart_rows_and_persists_reviewable_outputs(
    tmp_path: Path,
) -> None:
    database_path = _build_fixture_database(tmp_path)
    _dbt_build(database_path, "mart_transactions")
    repository = EnrichmentRepository(database_path)
    merchant = repository.create_merchant("MetroMart")
    repository.confirm_alias("METRO MART", merchant.merchant_id)

    result = EnrichmentService(repository).refresh()
    _dbt_build(database_path, "mart_recurring_groups mart_transactions")

    assert result.transaction_count == 864
    assert result.confirmed_merchant_count > 0
    assert result.recurring_candidate_count >= 2
    with duckdb.connect(str(database_path), read_only=True) as connection:
        assert connection.execute(
            "select count(*) from transaction_merchant_annotations"
        ).fetchone()[0] == 864
        assert connection.execute("select count(*) from raw_transactions").fetchone()[0] == 864
        assert connection.execute(
            "select count(*) from analytics.mart_recurring_groups"
        ).fetchone()[0] == result.recurring_candidate_count
        assert connection.execute(
            """
            select count(*) from analytics.mart_transactions
            where recurring_group_id is not null
            """
        ).fetchone()[0] == 0


def test_refresh_fails_when_the_trusted_mart_is_unavailable(tmp_path: Path) -> None:
    repository = EnrichmentRepository(tmp_path / "spend-memory.duckdb")

    with pytest.raises(RuntimeError, match="^trusted_mart_unavailable$"):
        EnrichmentService(repository).refresh()


def test_refresh_assigns_matching_trusted_rows_to_confirmed_counterparty_aliases(
    tmp_path: Path,
) -> None:
    database_path = _build_fixture_database(tmp_path)
    _dbt_build(database_path, "mart_transactions")
    repository = EnrichmentRepository(database_path)
    counterparty = repository.create_counterparty("Weekend groceries")
    repository.confirm_counterparty_alias("METRO MART", counterparty.counterparty_id)

    EnrichmentService(repository).refresh()

    descriptions = [
        row.description
        for row in repository.list_counterparty_transactions(counterparty.counterparty_id)
    ]
    assert descriptions and set(descriptions) == {"METRO MART", "METRO-MART"}


def test_refresh_keeps_an_explicit_counterparty_assignment_over_an_alias(
    tmp_path: Path,
) -> None:
    database_path = _build_fixture_database(tmp_path)
    _dbt_build(database_path, "mart_transactions")
    repository = EnrichmentRepository(database_path)
    alias_counterparty = repository.create_counterparty("Weekend groceries")
    manual_counterparty = repository.create_counterparty("Family transfer")
    repository.confirm_counterparty_alias("METRO MART", alias_counterparty.counterparty_id)
    transaction = next(
        item
        for item in repository.list_trusted_transactions()
        if item.normalized_description == "metro mart"
    )
    repository.assign_counterparty_transactions(
        manual_counterparty.counterparty_id, [transaction.raw_transaction_id]
    )

    EnrichmentService(repository).refresh()

    manual_ids = {
        item.raw_transaction_id
        for item in repository.list_counterparty_transactions(manual_counterparty.counterparty_id)
    }
    alias_ids = {
        item.raw_transaction_id
        for item in repository.list_counterparty_transactions(alias_counterparty.counterparty_id)
    }
    assert transaction.raw_transaction_id in manual_ids
    assert transaction.raw_transaction_id not in alias_ids
