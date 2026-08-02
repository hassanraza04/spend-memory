from __future__ import annotations

from datetime import date
from pathlib import Path
from uuid import uuid4

import duckdb
import pytest
from spend_memory.enrichment.categories import CategoryResolver
from spend_memory.enrichment.models import (
    CategoryDecision,
    Merchant,
    MerchantMatch,
    TrustedTransaction,
)
from spend_memory.enrichment.repository import EnrichmentRepository


@pytest.fixture
def repository(tmp_path: Path) -> EnrichmentRepository:
    return EnrichmentRepository(tmp_path / "spend-memory.duckdb")


def _transaction() -> TrustedTransaction:
    return TrustedTransaction(
        raw_transaction_id=uuid4(),
        account_identity="synthetic-account",
        transaction_date=date(2026, 1, 1),
        description="MetroMart",
        normalized_description="metromart",
        currency="AED",
        amount_minor=100,
        direction="debit",
    )


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


def _store_raw_transaction(
    repository: EnrichmentRepository, transaction: TrustedTransaction
) -> None:
    document_id = uuid4()
    run_id = uuid4()
    with duckdb.connect(str(repository.database_path)) as connection:
        connection.execute(
            """
            INSERT INTO source_documents (
                document_id, sha256_hex, original_filename, mime_type, byte_size,
                storage_filename
            ) VALUES (?, ?, 'test.csv', 'text/csv', 0, 'test.csv')
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
            ) VALUES (?, ?, 1, '2026-01-01', 'MetroMart', '-100', 'synthetic', 1)
            """,
            [transaction.raw_transaction_id, run_id],
        )


def test_transaction_override_wins_over_confirmed_merchant_category(
    repository: EnrichmentRepository,
) -> None:
    merchant = repository.create_merchant("MetroMart")
    groceries = repository.create_category("Groceries")
    gifts = repository.create_category("Gifts")
    repository.assign_merchant_category(merchant.merchant_id, groceries.category_id)
    transaction = _transaction()
    _store_raw_transaction(repository, transaction)
    repository.set_transaction_category_override(transaction.raw_transaction_id, gifts.category_id)

    result = CategoryResolver(repository).resolve(transaction, _confirmed_match(merchant))

    assert result == CategoryDecision(gifts.category_id, "Gifts", "transaction_override")


def test_confirmed_merchant_category_applies_without_an_override(
    repository: EnrichmentRepository,
) -> None:
    merchant = repository.create_merchant("MetroMart")
    groceries = repository.create_category("Groceries")
    repository.assign_merchant_category(merchant.merchant_id, groceries.category_id)

    result = CategoryResolver(repository).resolve(_transaction(), _confirmed_match(merchant))

    assert result == CategoryDecision(groceries.category_id, "Groceries", "merchant_assignment")


def test_suggested_merchant_does_not_assign_a_category(
    repository: EnrichmentRepository,
) -> None:
    merchant = repository.create_merchant("MetroMart")
    category = repository.create_category("Groceries")
    repository.assign_merchant_category(merchant.merchant_id, category.category_id)

    result = CategoryResolver(repository).resolve(_transaction(), _suggested_match(merchant))

    assert result == CategoryDecision(None, "Uncategorized", "none")
