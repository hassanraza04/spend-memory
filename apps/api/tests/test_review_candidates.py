from __future__ import annotations

from datetime import date
from pathlib import Path
from uuid import UUID, uuid4

import duckdb
from spend_memory.enrichment.models import MerchantMatch, TrustedTransaction
from spend_memory.enrichment.normalization import normalize_descriptor
from spend_memory.enrichment.repository import EnrichmentRepository
from spend_memory.enrichment.review import (
    find_duplicate_candidates,
    find_unusual_spend_candidates,
)


def _transaction(
    transaction_date: str,
    amount_minor: int,
    description: str,
    *,
    account_identity: str | None = "synthetic-account",
    direction: str = "debit",
    raw_id: UUID,
) -> TrustedTransaction:
    return TrustedTransaction(
        raw_transaction_id=raw_id,
        account_identity=account_identity,
        transaction_date=date.fromisoformat(transaction_date),
        description=description,
        normalized_description=normalize_descriptor(description),
        currency="AED",
        amount_minor=amount_minor,
        direction=direction,
    )


def test_same_day_same_debit_is_a_duplicate_review_candidate() -> None:
    candidates = find_duplicate_candidates(
        [
            _transaction("2026-03-12", 12500, "METRO MART", raw_id=UUID(int=1)),
            _transaction("2026-03-12", 12500, "Metro Mart", raw_id=UUID(int=2)),
        ],
        matches_by_transaction_id={},
    )

    assert candidates[0].raw_transaction_ids == (UUID(int=1), UUID(int=2))
    assert candidates[0].confidence == 1.0


def test_confirmed_merchant_matches_allow_different_descriptors() -> None:
    merchant_id = UUID(int=100)
    transactions = [
        _transaction("2026-03-12", 12500, "METRO MART", raw_id=UUID(int=1)),
        _transaction("2026-03-13", 12500, "MetroMart POS", raw_id=UUID(int=2)),
    ]
    matches = {
        transaction.raw_transaction_id: MerchantMatch(
            merchant_id, "MetroMart", "confirmed", 1.0, "confirmed_alias", {}
        )
        for transaction in transactions
    }

    assert find_duplicate_candidates(transactions, matches)[0].raw_transaction_ids == (
        UUID(int=1),
        UUID(int=2),
    )


def test_one_confirmed_merchant_uses_the_equal_normalized_descriptor() -> None:
    transactions = [
        _transaction("2026-03-12", 12500, "METRO MART", raw_id=UUID(int=1)),
        _transaction("2026-03-12", 12500, "Metro Mart", raw_id=UUID(int=2)),
    ]
    matches = {
        UUID(int=1): MerchantMatch(
            UUID(int=100), "MetroMart", "confirmed", 1.0, "confirmed_alias", {}
        )
    }

    assert find_duplicate_candidates(transactions, matches)[0].raw_transaction_ids == (
        UUID(int=1),
        UUID(int=2),
    )


def test_refund_reversal_and_legitimate_repeat_are_not_duplicate_candidates() -> None:
    rows = [
        _transaction("2026-03-12", 12500, "METRO MART", raw_id=UUID(int=1)),
        _transaction(
            "2026-03-12", 12500, "METRO MART", direction="credit", raw_id=UUID(int=2)
        ),
        _transaction("2026-03-20", 12500, "METRO MART", raw_id=UUID(int=3)),
    ]

    assert find_duplicate_candidates(rows, matches_by_transaction_id={}) == []


def test_missing_account_identity_does_not_create_duplicate_candidates() -> None:
    rows = [
        _transaction(
            "2026-03-12", 12500, "METRO MART", account_identity=None, raw_id=UUID(int=1)
        ),
        _transaction(
            "2026-03-12", 12500, "METRO MART", account_identity=None, raw_id=UUID(int=2)
        ),
    ]

    assert find_duplicate_candidates(rows, matches_by_transaction_id={}) == []


def test_unusual_candidate_needs_history_and_uses_median_absolute_deviation() -> None:
    rows = [
        _transaction(f"2026-03-0{index}", amount, "CORNER SHOP", raw_id=UUID(int=index))
        for index, amount in enumerate((100, 110, 90, 105, 95, 500), start=1)
    ]

    candidates = find_unusual_spend_candidates(rows, matches_by_transaction_id={})

    assert [candidate.raw_transaction_id for candidate in candidates] == [UUID(int=6)]
    assert candidates[0].evidence == {
        "group_key": "synthetic-account|descriptor:corner shop|AED",
        "median_amount_minor_twice": 200,
        "mad_minor_twice": 10,
        "observed_amount_minor": 500,
        "sample_size": 5,
    }
    assert find_unusual_spend_candidates(rows[:2], matches_by_transaction_id={}) == []


def test_zero_mad_does_not_create_an_unusual_spend_candidate() -> None:
    rows = [
        _transaction(f"2026-03-0{index}", 100, "CORNER SHOP", raw_id=UUID(int=index))
        for index in range(1, 6)
    ] + [_transaction("2026-03-06", 500, "CORNER SHOP", raw_id=UUID(int=6))]

    assert find_unusual_spend_candidates(rows, matches_by_transaction_id={}) == []


def test_missing_account_identity_does_not_pool_unusual_spend_history() -> None:
    rows = [
        _transaction(
            f"2026-03-0{index}",
            amount,
            "CORNER SHOP",
            account_identity=None,
            raw_id=UUID(int=index),
        )
        for index, amount in enumerate((100, 110, 90, 105, 95, 500), start=1)
    ]

    assert find_unusual_spend_candidates(rows, matches_by_transaction_id={}) == []


def test_unusual_evidence_preserves_even_history_median_and_mad() -> None:
    rows = [
        _transaction(
            f"2026-03-0{index}", amount, "CORNER SHOP", raw_id=UUID(int=index)
        )
        for index, amount in enumerate((100, 101, 102, 103, 104, 105, 200), start=1)
    ]

    candidate = find_unusual_spend_candidates(rows, matches_by_transaction_id={})[0]

    assert candidate.evidence["median_amount_minor_twice"] == 205
    assert candidate.evidence["mad_minor_twice"] == 3
    assert candidate.evidence["sample_size"] == 6


def test_replacing_review_candidates_only_replaces_generated_rows(
    tmp_path: Path,
) -> None:
    repository = EnrichmentRepository(tmp_path / "spend-memory.duckdb")
    _store_raw_transactions(
        repository, [UUID(int=value) for value in (1, 2, 11, 12, 13, 14, 15, 16)]
    )
    duplicate = find_duplicate_candidates(
        [
            _transaction("2026-03-12", 12500, "METRO MART", raw_id=UUID(int=1)),
            _transaction("2026-03-12", 12500, "METRO MART", raw_id=UUID(int=2)),
        ],
        {},
    )
    unusual = find_unusual_spend_candidates(
        [
            _transaction(
                f"2026-03-0{index}", amount, "CORNER SHOP", raw_id=UUID(int=index + 10)
            )
            for index, amount in enumerate((100, 110, 90, 105, 95, 500), start=1)
        ],
        {},
    )

    repository.replace_duplicate_candidates(duplicate)
    repository.replace_unusual_spend_candidates(unusual)
    repository.replace_duplicate_candidates([])

    with duckdb.connect(str(repository.database_path), read_only=True) as connection:
        assert connection.execute(
            "SELECT count(*) FROM duplicate_review_candidates"
        ).fetchone() == (0,)
        assert connection.execute(
            "SELECT raw_transaction_id, confidence FROM unusual_spend_candidates"
        ).fetchall() == [(UUID(int=16), 1.0)]


def _store_raw_transactions(
    repository: EnrichmentRepository, raw_transaction_ids: list[UUID]
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
        connection.executemany(
            """
            INSERT INTO raw_transactions (
                raw_transaction_id, import_run_id, source_ordinal, date_text,
                description_text, amount_text, extraction_method, extraction_confidence
            ) VALUES (?, ?, ?, '2026-03-01', 'synthetic', '-100', 'synthetic', 1)
            """,
            [
                [raw_transaction_id, run_id, ordinal]
                for ordinal, raw_transaction_id in enumerate(raw_transaction_ids)
            ],
        )
