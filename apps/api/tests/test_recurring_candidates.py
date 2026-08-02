from __future__ import annotations

from datetime import date
from pathlib import Path
from uuid import uuid4

import duckdb
import pytest
from spend_memory.enrichment.models import MerchantMatch, TrustedTransaction
from spend_memory.enrichment.normalization import normalize_descriptor
from spend_memory.enrichment.recurring import detect_recurring_candidates
from spend_memory.enrichment.repository import EnrichmentRepository


def _transaction(
    transaction_date: str, amount_minor: int, description: str, *, direction: str = "debit"
) -> TrustedTransaction:
    return TrustedTransaction(
        raw_transaction_id=uuid4(),
        account_identity="synthetic-account",
        transaction_date=date.fromisoformat(transaction_date),
        description=description,
        normalized_description=normalize_descriptor(description),
        currency="AED",
        amount_minor=amount_minor,
        direction=direction,
    )


def test_monthly_candidate_explains_dates_amount_range_and_next_window() -> None:
    result = detect_recurring_candidates(
        [
            _transaction("2026-01-02", 2999, "STREAMBOX MONTHLY"),
            _transaction("2026-02-03", 2999, "STREAMBOX MONTHLY"),
            _transaction("2026-03-02", 3099, "STREAMBOX MONTHLY"),
        ],
        matches_by_transaction_id={},
    )

    assert result[0].cadence == "monthly"
    assert result[0].amount_min_minor == 2999
    assert result[0].amount_max_minor == 3099
    assert result[0].expected_next_start.isoformat() == "2026-03-30"
    assert result[0].expected_next_end.isoformat() == "2026-04-05"
    assert result[0].evidence["transaction_dates"] == "2026-01-02,2026-02-03,2026-03-02"


@pytest.mark.parametrize(
    ("cadence", "dates"),
    [
        ("weekly", ("2026-01-02", "2026-01-09", "2026-01-16")),
        ("quarterly", ("2026-01-02", "2026-04-02", "2026-07-02")),
        ("annual", ("2024-01-02", "2025-01-02", "2026-01-02")),
    ],
)
def test_supported_cadences_create_candidates(cadence: str, dates: tuple[str, str, str]) -> None:
    result = detect_recurring_candidates(
        [_transaction(value, 1000, "REPEAT SERVICE") for value in dates],
        matches_by_transaction_id={},
    )

    assert [candidate.cadence for candidate in result] == [cadence]


def test_amount_tolerance_allows_ten_percent_and_rejects_more() -> None:
    accepted = detect_recurring_candidates(
        [
            _transaction("2026-01-02", 1000, "FLEX PLAN"),
            _transaction("2026-02-02", 1100, "FLEX PLAN"),
            _transaction("2026-03-02", 1000, "FLEX PLAN"),
        ],
        matches_by_transaction_id={},
    )
    rejected = detect_recurring_candidates(
        [
            _transaction("2026-01-02", 1000, "FLEX PLAN"),
            _transaction("2026-02-02", 1112, "FLEX PLAN"),
            _transaction("2026-03-02", 1000, "FLEX PLAN"),
        ],
        matches_by_transaction_id={},
    )

    assert len(accepted) == 1
    assert rejected == []


def test_confirmed_merchant_groups_different_descriptors() -> None:
    merchant_id = uuid4()
    transactions = [
        _transaction("2026-01-02", 1000, "VIDEO PLAN"),
        _transaction("2026-02-02", 1000, "VIDEO SERVICE"),
        _transaction("2026-03-02", 1000, "VIDEO SUBSCRIPTION"),
    ]
    matches = {
        transaction.raw_transaction_id: MerchantMatch(
            merchant_id, "VideoCo", "confirmed", 1.0, "confirmed_alias", {}
        )
        for transaction in transactions
    }

    result = detect_recurring_candidates(transactions, matches)

    assert len(result) == 1
    assert result[0].merchant_id == merchant_id


def test_credits_and_irregular_repeats_are_not_recurring_candidates() -> None:
    transactions = [
        _transaction("2026-01-02", 1000, "CREDIT PLAN", direction="credit"),
        _transaction("2026-02-02", 1000, "CREDIT PLAN", direction="credit"),
        _transaction("2026-03-02", 1000, "CREDIT PLAN", direction="credit"),
        _transaction("2026-01-02", 1000, "IRREGULAR PLAN"),
        _transaction("2026-02-10", 1000, "IRREGULAR PLAN"),
        _transaction("2026-04-25", 1000, "IRREGULAR PLAN"),
    ]

    assert detect_recurring_candidates(transactions, matches_by_transaction_id={}) == []


def test_replacing_recurring_candidates_keeps_only_review_candidates(tmp_path: Path) -> None:
    repository = EnrichmentRepository(tmp_path / "spend-memory.duckdb")
    first = detect_recurring_candidates(
        [_transaction(value, 1000, "FIRST PLAN") for value in ("2026-01-02", "2026-02-02", "2026-03-02")],
        matches_by_transaction_id={},
    )
    second = detect_recurring_candidates(
        [_transaction(value, 2000, "SECOND PLAN") for value in ("2026-01-02", "2026-02-02", "2026-03-02")],
        matches_by_transaction_id={},
    )

    repository.replace_recurring_candidates(first)
    repository.replace_recurring_candidates(second)
    repository.replace_recurring_candidates([])

    with duckdb.connect(str(repository.database_path), read_only=True) as connection:
        assert connection.execute(
            "SELECT candidate_key, status, amount_min_minor FROM recurring_candidates"
        ).fetchall() == []
