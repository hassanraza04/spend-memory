from __future__ import annotations

from datetime import date
from uuid import UUID

import pytest
from spend_memory.enrichment.models import CategoryDecision, TrustedTransaction
from spend_memory.enrichment.search import (
    SearchQueryError,
    SearchRow,
    parse_search_query,
    search_transactions,
)


def _search_rows() -> list[SearchRow]:
    groceries = CategoryDecision(UUID(int=1), "Groceries", "merchant_assignment")
    return [
        SearchRow(
            TrustedTransaction(
                UUID(int=2), "synthetic", date(2026, 1, 3), "METRO MART", "metro mart",
                "AED", 1200, "debit",
            ),
            groceries,
            "MetroMart",
            "none",
        ),
        SearchRow(
            TrustedTransaction(
                UUID(int=4),
                "synthetic",
                date(2026, 1, 4),
                "Coffee Corner Online",
                "coffee corner",
                "USD",
                900,
                "credit",
            ),
            CategoryDecision(UUID(int=7), "Dining", "merchant_assignment"),
            "Coffee Corner",
            "recurring",
        ),
        SearchRow(
            TrustedTransaction(
                UUID(int=5),
                "synthetic",
                date(2026, 1, 5),
                "METRO MART REFUND",
                "metro mart refund",
                "AED",
                1200,
                "credit",
            ),
            groceries,
            "MetroMart",
            "review",
        ),
        SearchRow(
            TrustedTransaction(
                UUID(int=6),
                "synthetic",
                date(2026, 1, 6),
                "Fuel Stop #123",
                "fuel stop",
                "AED",
                5000,
                "debit",
            ),
            CategoryDecision(UUID(int=8), "Transport", "merchant_assignment"),
            "Fuel Stop",
            "unusual",
        ),
        SearchRow(
            TrustedTransaction(
                UUID(int=3), "synthetic", date(2026, 1, 2), "MetroMart POS", "metro mart",
                "AED", 1500, "debit",
            ),
            groceries,
            "MetroMart",
            "none",
        ),
    ]


def test_search_combines_structured_filters_and_free_text() -> None:
    query = parse_search_query("currency:AED direction:debit after:2026-01-01 metro")

    results = search_transactions(_search_rows(), query)

    assert [result.transaction.description for result in results] == ["METRO MART", "MetroMart POS"]


def test_search_rejects_unknown_filter_and_invalid_amount_range() -> None:
    with pytest.raises(SearchQueryError, match="unknown_filter"):
        parse_search_query("planet:mars")
    with pytest.raises(SearchQueryError, match="invalid_amount_range"):
        parse_search_query("amount:50..10")


_EVALUATION_QUERIES = (
    ("metro", 5, None), ("metro mart", 5, None), ("METRO MART", 5, None),
    ("metromart", 3, None), ("mart", 5, None), ("coffee", 4, None),
    ("corner", 4, None), ("fuel", 6, None), ("stop", 6, None),
    ("refund", 5, None), ("currency:AED", 6, None), ("currency:USD", 4, None),
    ("currency:EUR", None, None), ("direction:debit", 6, None),
    ("direction:credit", 5, None), ("after:2026-01-05", 6, None),
    ("before:2026-01-04", 2, None), ("after:2026-01-03 before:2026-01-06", 5, None),
    ("merchant:MetroMart", 5, None), ("merchant:Coffee", None, None),
    ("merchant:Coffee Corner", None, None), ("category:Groceries", 5, None),
    ("category:Dining", 4, None), ("category:Transport", 6, None),
    ("amount:1200..1200", 5, None), ("amount:0..1000", 4, None),
    ("amount:5000..9000", 6, None), ("state:none", 2, None),
    ("state:recurring", 4, None), ("state:review", 5, None),
    ("state:unusual", 6, None), ("currency:AED metro", 5, None),
    ("currency:USD metro", None, None), ("direction:credit metro", 5, None),
    ("category:Groceries metro", 5, None), ("merchant:MetroMart refund", 5, None),
    ("amount:1000..2000 metro", 5, None), ("after:2026-01-01 metro", 5, None),
    ("before:2026-01-06 metro", 5, None), ("", None, None),
    ("planet:mars", None, "unknown_filter"), ("amount:50..10", None, "invalid_amount_range"),
    ("amount:abc", None, "invalid_amount_range"), ("after:not-a-date", None, "invalid_date"),
    ("direction:transfer", None, "invalid_direction"),
    ("currency:AED currency:USD", None, "duplicate_filter"),
    ("state:review state:none", None, "duplicate_filter"),
    ("amount:1..2..3", None, "invalid_amount_range"), ("merchant:", None, "invalid_filter"),
    ("before:2026-13-01", None, "invalid_date"),
)


def test_local_lexical_baseline_has_mrr_at_10_of_one() -> None:
    assert len(_EVALUATION_QUERIES) == 50

    reciprocal_ranks: list[float] = []
    for query_text, expected_id, error_code in _EVALUATION_QUERIES:
        if error_code is not None:
            with pytest.raises(SearchQueryError, match=error_code):
                parse_search_query(query_text)
            continue
        results = search_transactions(_search_rows(), parse_search_query(query_text))
        if expected_id is None:
            assert results == []
            continue
        identifiers = [result.transaction.raw_transaction_id.int for result in results[:10]]
        assert identifiers[0] == expected_id
        reciprocal_ranks.append(1 / (identifiers.index(expected_id) + 1))

    assert sum(reciprocal_ranks) / len(reciprocal_ranks) == 1.0
