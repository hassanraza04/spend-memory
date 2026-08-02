from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path
from uuid import UUID, uuid4

import duckdb
import pytest
from spend_memory.enrichment.models import MerchantMatch, TrustedTransaction
from spend_memory.enrichment.normalization import normalize_descriptor
from spend_memory.enrichment.recurring import detect_recurring_candidates
from spend_memory.enrichment.repository import EnrichmentRepository


def _transaction(
    transaction_date: str,
    amount_minor: int,
    description: str,
    *,
    direction: str = "debit",
    raw_id: UUID | None = None,
) -> TrustedTransaction:
    return TrustedTransaction(
        raw_transaction_id=raw_id or uuid4(),
        account_identity="synthetic-account",
        transaction_date=date.fromisoformat(transaction_date),
        description=description,
        normalized_description=normalize_descriptor(description),
        currency="AED",
        amount_minor=amount_minor,
        direction=direction,
    )


def test_monthly_candidate_explains_dates_amount_range_and_next_window() -> None:
    transactions = [
        _transaction("2026-01-02", 2999, "STREAMBOX MONTHLY"),
        _transaction("2026-02-03", 2999, "STREAMBOX MONTHLY"),
        _transaction("2026-03-02", 3099, "STREAMBOX MONTHLY"),
    ]
    result = detect_recurring_candidates(transactions, matches_by_transaction_id={})

    assert result[0].cadence == "monthly"
    assert result[0].amount_min_minor == 2999
    assert result[0].amount_max_minor == 3099
    assert result[0].expected_next_start.isoformat() == "2026-03-30"
    assert result[0].expected_next_end.isoformat() == "2026-04-05"
    assert result[0].evidence["transaction_dates"] == "2026-01-02,2026-02-03,2026-03-02"
    assert result[0].raw_transaction_ids == tuple(
        transaction.raw_transaction_id for transaction in transactions
    )
    assert result[0].evidence["amount_tolerance_basis_points"] == 1000


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


def test_amount_tolerance_uses_an_exact_integer_ratio() -> None:
    assert detect_recurring_candidates(
        [
            _transaction("2026-01-02", 14, "TINY PLAN"),
            _transaction("2026-02-02", 15, "TINY PLAN"),
            _transaction("2026-03-02", 14, "TINY PLAN"),
        ],
        matches_by_transaction_id={},
    )
    assert detect_recurring_candidates(
        [
            _transaction("2026-01-02", 13, "TINY PLAN"),
            _transaction("2026-02-02", 15, "TINY PLAN"),
            _transaction("2026-03-02", 13, "TINY PLAN"),
        ],
        matches_by_transaction_id={},
    ) == []


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


def test_replacing_recurring_candidates_activates_one_complete_generation(
    tmp_path: Path,
) -> None:
    repository = EnrichmentRepository(tmp_path / "spend-memory.duckdb")
    first = detect_recurring_candidates(
        [_transaction(value, 1000, "FIRST PLAN") for value in ("2026-01-02", "2026-02-02", "2026-03-02")],
        matches_by_transaction_id={},
    )
    second = detect_recurring_candidates(
        [_transaction(value, 2000, "SECOND PLAN") for value in ("2026-01-02", "2026-02-02", "2026-03-02")],
        matches_by_transaction_id={},
    )

    _store_raw_transactions(
        repository,
        [
            *first[0].raw_transaction_ids,
            *second[0].raw_transaction_ids,
        ],
    )

    repository.replace_recurring_candidates(first)
    assert _active_recurring_rows(repository) == [
        (first[0].candidate_key, 1000, raw_transaction_id)
        for raw_transaction_id in sorted(first[0].raw_transaction_ids)
    ]
    repository.replace_recurring_candidates(second)
    assert _active_recurring_rows(repository) == [
        (second[0].candidate_key, 2000, raw_transaction_id)
        for raw_transaction_id in sorted(second[0].raw_transaction_ids)
    ]


def test_failed_recurring_refresh_keeps_prior_active_generation_and_members(
    tmp_path: Path,
) -> None:
    repository = EnrichmentRepository(tmp_path / "spend-memory.duckdb")
    first = detect_recurring_candidates(
        [
            _transaction(value, 1000, "FIRST PLAN")
            for value in ("2026-01-02", "2026-02-02", "2026-03-02")
        ],
        matches_by_transaction_id={},
    )
    second = detect_recurring_candidates(
        [
            _transaction(value, 2000, "SECOND PLAN")
            for value in ("2026-01-02", "2026-02-02", "2026-03-02")
        ],
        matches_by_transaction_id={},
    )
    _store_raw_transactions(repository, list(first[0].raw_transaction_ids))
    repository.replace_recurring_candidates(first)
    active_before = _active_recurring_rows(repository)

    missing_raw_transaction_id = uuid4()
    invalid_candidate = replace(
        second[0], raw_transaction_ids=(missing_raw_transaction_id,)
    )
    with pytest.raises(duckdb.ConstraintException):
        repository.replace_recurring_candidates([invalid_candidate])

    assert _active_recurring_rows(repository) == active_before
    with duckdb.connect(str(repository.database_path), read_only=True) as connection:
        assert connection.execute(
            "SELECT count(*) FROM recurring_candidate_generations"
        ).fetchone() == (2,)


def test_empty_recurring_refresh_activates_an_empty_generation(tmp_path: Path) -> None:
    repository = EnrichmentRepository(tmp_path / "spend-memory.duckdb")
    first = detect_recurring_candidates(
        [
            _transaction(value, 1000, "FIRST PLAN")
            for value in ("2026-01-02", "2026-02-02", "2026-03-02")
        ],
        matches_by_transaction_id={},
    )
    _store_raw_transactions(repository, list(first[0].raw_transaction_ids))
    repository.replace_recurring_candidates(first)
    with duckdb.connect(str(repository.database_path), read_only=True) as connection:
        previous_generation_id = connection.execute(
            "SELECT active_generation_id FROM recurring_candidate_state"
        ).fetchone()[0]

    repository.replace_recurring_candidates([])

    with duckdb.connect(str(repository.database_path), read_only=True) as connection:
        assert connection.execute(
            "SELECT active_generation_id FROM recurring_candidate_state"
        ).fetchone()[0] != previous_generation_id
        assert connection.execute(
            """
            SELECT count(*)
            FROM recurring_candidates c
            JOIN recurring_candidate_state s
              ON s.active_generation_id = c.generation_id
            """
        ).fetchone() == (0,)
        assert connection.execute(
            "SELECT count(*) FROM recurring_candidates WHERE generation_id = ?",
            [previous_generation_id],
        ).fetchone() == (1,)
        assert connection.execute(
            """
            SELECT count(*)
            FROM recurring_candidate_members m
            JOIN recurring_candidates c USING (recurring_candidate_id)
            WHERE c.generation_id = ?
            """,
            [previous_generation_id],
        ).fetchone() == (3,)


def _active_recurring_rows(
    repository: EnrichmentRepository,
) -> list[tuple[str, int, UUID]]:
    with duckdb.connect(str(repository.database_path), read_only=True) as connection:
        return connection.execute(
            """
            SELECT c.candidate_key, c.amount_min_minor, m.raw_transaction_id
            FROM recurring_candidate_state s
            JOIN recurring_candidates c
              ON c.generation_id = s.active_generation_id
            JOIN recurring_candidate_members m USING (recurring_candidate_id)
            ORDER BY m.raw_transaction_id
            """
        ).fetchall()


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
