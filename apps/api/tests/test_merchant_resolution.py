from __future__ import annotations

from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest
from spend_memory.enrichment.merchants import (
    MerchantResolver,
    evaluate_merchant_matches,
    retrieval_corpus,
)
from spend_memory.enrichment.models import MerchantMatch, TrustedTransaction
from spend_memory.enrichment.normalization import normalize_descriptor
from spend_memory.enrichment.repository import EnrichmentRepository


@pytest.fixture
def repository(tmp_path: Path) -> EnrichmentRepository:
    return EnrichmentRepository(tmp_path / "spend-memory.duckdb")


def _transaction(description: str, normalized_description: str | None = None) -> TrustedTransaction:
    return TrustedTransaction(
        raw_transaction_id=uuid4(),
        account_identity="synthetic-account",
        transaction_date=date(2026, 1, 1),
        description=description,
        normalized_description=normalized_description or normalize_descriptor(description),
        currency="AED",
        amount_minor=100,
        direction="debit",
    )


def test_normalize_descriptor_removes_known_statement_noise() -> None:
    assert normalize_descriptor("POS METRO-MART #A9172 TERM 004") == "metro mart"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("", ""),
        ("Payment Corner-Shop", "corner shop"),
        ("Card Cafe, Ref 001", "cafe"),
        ("Metro Mart Online", "metro mart"),
        ("Cafe & Bakery!!!", "cafe bakery"),
        ("Studio 54 Cafe", "studio 54 cafe"),
    ],
)
def test_normalize_descriptor_handles_only_documented_noise(
    value: str, expected: str
) -> None:
    assert normalize_descriptor(value) == expected


def test_exact_confirmed_alias_is_a_confirmed_match(
    repository: EnrichmentRepository,
) -> None:
    merchant = repository.create_merchant("MetroMart")
    repository.confirm_alias("METRO MART", merchant.merchant_id)

    result = MerchantResolver(repository).resolve(
        _transaction("MetroMart POS", normalized_description="metro mart")
    )

    assert result == MerchantMatch(
        merchant.merchant_id,
        "MetroMart",
        "confirmed",
        1.0,
        "confirmed_alias",
        {"normalized_descriptor": "metro mart"},
    )


def test_trailing_payment_channel_becomes_an_exact_confirmed_match(
    repository: EnrichmentRepository,
) -> None:
    merchant = repository.create_merchant("MetroMart")
    repository.confirm_alias("METRO MART", merchant.merchant_id)

    result = MerchantResolver(repository).resolve(_transaction("METRO MART ONLINE"))

    assert result.status == "confirmed"
    assert result.merchant_id == merchant.merchant_id
    assert result.confidence == 1.0


def test_retrieval_is_a_suggestion_and_never_a_confirmed_fact(
    repository: EnrichmentRepository,
) -> None:
    merchant = repository.create_merchant("MetroMart")
    repository.confirm_alias("METRO MART", merchant.merchant_id)

    result = MerchantResolver(repository).resolve(_transaction("METRO MAR"))

    assert result.status == "suggested"
    assert result.merchant_id == merchant.merchant_id
    assert 0 < result.confidence < 1
    assert repository.find_confirmed_alias("METRO MAR") is None


def test_currency_observation_only_bonuses_compatible_candidate(
    repository: EnrichmentRepository,
) -> None:
    merchant = repository.create_merchant("MetroMart")
    repository.confirm_alias("METRO MART", merchant.merchant_id)
    repository.record_confirmed_merchant_currency(merchant.merchant_id, "AED")

    result = MerchantResolver(repository).resolve(_transaction("METRO MAR"))

    assert result.evidence["currency_signal"] == "compatible"


def test_merchant_evaluation_keeps_held_out_variants_out_of_the_corpus() -> None:
    metromart_id = uuid4()
    cafe_id = uuid4()
    examples = [
        (metromart_id, "MetroMart", "METRO MART"),
        (metromart_id, "MetroMart", "METRO MART ONLINE"),
        (cafe_id, "Cafe Lane", "CAFE LANE"),
        (cafe_id, "Cafe Lane", "CAFE LANE DUBAI"),
    ]

    corpus = retrieval_corpus(examples, held_out_merchant_ids={metromart_id})
    evaluation = evaluate_merchant_matches(examples, held_out_merchant_ids={metromart_id})

    assert all(entry.merchant_id != metromart_id for entry in corpus)
    assert evaluation.precision == 1.0
    assert evaluation.coverage == 0.5
    assert evaluation.expected_calibration_error >= 0.0
