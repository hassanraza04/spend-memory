from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from spend_memory.enrichment.models import (
    CategoryDecision,
    SearchQuery,
    SearchResult,
    TrustedTransaction,
)
from spend_memory.enrichment.normalization import normalize_descriptor

_FILTERS = {"after", "before", "currency", "direction", "merchant", "category", "amount", "state"}


class SearchQueryError(ValueError):
    pass


@dataclass(frozen=True)
class SearchRow:
    transaction: TrustedTransaction
    category: CategoryDecision
    merchant_name: str | None
    state: str


def parse_search_query(query: str) -> SearchQuery:
    values: dict[str, str] = {}
    text: list[str] = []
    for token in query.split():
        if ":" not in token:
            text.append(token)
            continue
        key, value = token.split(":", 1)
        if key not in _FILTERS:
            raise SearchQueryError("unknown_filter")
        if not value or key in values:
            raise SearchQueryError("duplicate_filter" if key in values else "invalid_filter")
        values[key] = value
    after = _date(values.get("after"))
    before = _date(values.get("before"))
    if values.get("direction") not in {None, "debit", "credit"}:
        raise SearchQueryError("invalid_direction")
    amount_min, amount_max = _amount(values.get("amount"))
    return SearchQuery(
        after=after,
        before=before,
        currency=values.get("currency"),
        direction=values.get("direction"),
        merchant=values.get("merchant"),
        category=values.get("category"),
        amount_min_minor=amount_min,
        amount_max_minor=amount_max,
        state=values.get("state"),
        text=" ".join(text),
    )


def search_transactions(
    rows: Iterable[SearchRow], query: SearchQuery
) -> list[SearchResult]:
    if not query.text and not _has_filter(query):
        return []
    query_normalized = normalize_descriptor(query.text)
    query_tokens = set(query_normalized.split())
    results = []
    for row in rows:
        if not _matches(row, query):
            continue
        score = _score(row.transaction, query_normalized, query_tokens)
        if query_normalized and score == 0:
            continue
        results.append(SearchResult(row.transaction, score))
    return sorted(
        results,
        key=lambda result: (
            -result.score,
            -result.transaction.transaction_date.toordinal(),
            str(result.transaction.raw_transaction_id),
        ),
    )


def _date(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise SearchQueryError("invalid_date") from error


def _amount(value: str | None) -> tuple[int | None, int | None]:
    if value is None:
        return None, None
    try:
        lower, upper = (int(part) for part in value.split(".."))
    except ValueError as error:
        raise SearchQueryError("invalid_amount_range") from error
    if lower > upper:
        raise SearchQueryError("invalid_amount_range")
    return lower, upper


def _has_filter(query: SearchQuery) -> bool:
    return any(value is not None for name, value in vars(query).items() if name != "text")


def _matches(row: SearchRow, query: SearchQuery) -> bool:
    transaction = row.transaction
    return (
        (query.after is None or transaction.transaction_date > query.after)
        and (query.before is None or transaction.transaction_date < query.before)
        and (query.currency is None or transaction.currency == query.currency)
        and (query.direction is None or transaction.direction == query.direction)
        and (query.merchant is None or _same_text(row.merchant_name, query.merchant))
        and (query.category is None or _same_text(row.category.category_label, query.category))
        and (query.amount_min_minor is None or transaction.amount_minor >= query.amount_min_minor)
        and (query.amount_max_minor is None or transaction.amount_minor <= query.amount_max_minor)
        and (query.state is None or row.state == query.state)
    )


def _same_text(value: str | None, expected: str) -> bool:
    return value is not None and value.casefold() == expected.casefold()


def _score(transaction: TrustedTransaction, query: str, query_tokens: set[str]) -> float:
    if not query:
        return 0.0
    descriptors = {normalize_descriptor(transaction.description), transaction.normalized_description}
    if query in descriptors:
        return 1.0
    token_sets = [set(value.split()) for value in descriptors]
    if any(query_tokens == tokens for tokens in token_sets):
        return 0.9
    return max((_jaccard(query_tokens, tokens) for tokens in token_sets), default=0.0)


def _jaccard(first: set[str], second: set[str]) -> float:
    return len(first & second) / len(first | second) if first and second else 0.0
