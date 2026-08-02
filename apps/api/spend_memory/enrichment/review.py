from __future__ import annotations

from collections import defaultdict
from datetime import date
from uuid import UUID

from spend_memory.enrichment.models import (
    DuplicateCandidate,
    MerchantMatch,
    TrustedTransaction,
    UnusualSpendCandidate,
)


def find_duplicate_candidates(
    transactions: list[TrustedTransaction],
    matches_by_transaction_id: dict[UUID, MerchantMatch],
) -> list[DuplicateCandidate]:
    candidates: list[DuplicateCandidate] = []
    for index, first in enumerate(transactions):
        for second in transactions[index + 1 :]:
            if not _is_duplicate_pair(first, second, matches_by_transaction_id):
                continue
            merchant_key = _duplicate_identity(first, second, matches_by_transaction_id)
            assert merchant_key is not None
            raw_transaction_ids = tuple(
                sorted((first.raw_transaction_id, second.raw_transaction_id))
            )
            candidates.append(
                DuplicateCandidate(
                    raw_transaction_ids=raw_transaction_ids,
                    confidence=1.0,
                    evidence={
                        "account_identity": first.account_identity or "",
                        "currency": first.currency,
                        "direction": first.direction,
                        "amount_minor": abs(first.amount_minor),
                        "date_distance_days": abs(
                            (first.transaction_date - second.transaction_date).days
                        ),
                        "merchant_key": merchant_key,
                    },
                )
            )
    return sorted(candidates, key=lambda candidate: candidate.raw_transaction_ids)


def find_unusual_spend_candidates(
    transactions: list[TrustedTransaction],
    matches_by_transaction_id: dict[UUID, MerchantMatch],
) -> list[UnusualSpendCandidate]:
    groups: dict[tuple[str | None, str, str], list[TrustedTransaction]] = defaultdict(
        list
    )
    for transaction in transactions:
        if transaction.direction == "debit" and transaction.account_identity is not None:
            groups[
                (
                    transaction.account_identity,
                    _merchant_key(transaction, matches_by_transaction_id),
                    transaction.currency,
                )
            ].append(transaction)

    candidates: list[UnusualSpendCandidate] = []
    for (account_identity, merchant_key, currency), rows in groups.items():
        history: list[int] = []
        rows.sort(key=lambda row: (row.transaction_date, str(row.raw_transaction_id)))
        for _, same_day_rows in _rows_by_date(rows):
            for row in same_day_rows:
                candidate = _unusual_candidate(
                    row, history, account_identity, merchant_key, currency
                )
                if candidate is not None:
                    candidates.append(candidate)
            history.extend(abs(row.amount_minor) for row in same_day_rows)
    return sorted(candidates, key=lambda candidate: str(candidate.raw_transaction_id))


def _is_duplicate_pair(
    first: TrustedTransaction,
    second: TrustedTransaction,
    matches_by_transaction_id: dict[UUID, MerchantMatch],
) -> bool:
    return (
        first.account_identity is not None
        and first.account_identity == second.account_identity
        and first.currency == second.currency
        and first.direction == second.direction
        and abs((first.transaction_date - second.transaction_date).days) <= 1
        and abs(first.amount_minor) == abs(second.amount_minor)
        and _duplicate_identity(first, second, matches_by_transaction_id) is not None
    )


def _duplicate_identity(
    first: TrustedTransaction,
    second: TrustedTransaction,
    matches_by_transaction_id: dict[UUID, MerchantMatch],
) -> str | None:
    first_match = _confirmed_merchant(first, matches_by_transaction_id)
    second_match = _confirmed_merchant(second, matches_by_transaction_id)
    if first_match is not None and second_match is not None:
        return f"merchant:{first_match}" if first_match == second_match else None
    return (
        f"descriptor:{first.normalized_description}"
        if first.normalized_description == second.normalized_description
        else None
    )


def _merchant_key(
    transaction: TrustedTransaction,
    matches_by_transaction_id: dict[UUID, MerchantMatch],
) -> str:
    merchant_id = _confirmed_merchant(transaction, matches_by_transaction_id)
    if merchant_id is not None:
        return f"merchant:{merchant_id}"
    return f"descriptor:{transaction.normalized_description}"


def _confirmed_merchant(
    transaction: TrustedTransaction,
    matches_by_transaction_id: dict[UUID, MerchantMatch],
) -> UUID | None:
    match = matches_by_transaction_id.get(transaction.raw_transaction_id)
    return (
        match.merchant_id
        if match is not None and match.status == "confirmed"
        else None
    )


def _rows_by_date(
    rows: list[TrustedTransaction],
) -> list[tuple[date, list[TrustedTransaction]]]:
    grouped: list[tuple[date, list[TrustedTransaction]]] = []
    for row in rows:
        if not grouped or grouped[-1][0] != row.transaction_date:
            grouped.append((row.transaction_date, []))
        grouped[-1][1].append(row)
    return grouped


def _unusual_candidate(
    row: TrustedTransaction,
    history: list[int],
    account_identity: str | None,
    merchant_key: str,
    currency: str,
) -> UnusualSpendCandidate | None:
    if len(history) < 5:
        return None
    median_amount_twice = _median_twice(history)
    deviations_twice = [
        abs(2 * value - median_amount_twice) for value in history
    ]
    mad_twice = _exact_median(deviations_twice)
    observed_amount = abs(row.amount_minor)
    if mad_twice == 0 or 2 * observed_amount <= median_amount_twice + 4 * mad_twice:
        return None
    return UnusualSpendCandidate(
        raw_transaction_id=row.raw_transaction_id,
        confidence=1.0,
        evidence={
            "group_key": f"{account_identity or ''}|{merchant_key}|{currency}",
            "median_amount_minor_twice": median_amount_twice,
            "mad_minor_twice": mad_twice,
            "observed_amount_minor": observed_amount,
            "sample_size": len(history),
        },
    )


def _median_twice(values: list[int]) -> int:
    ordered = sorted(values)
    middle = len(ordered) // 2
    return (
        ordered[middle] * 2
        if len(ordered) % 2
        else ordered[middle - 1] + ordered[middle]
    )


def _exact_median(values: list[int]) -> int:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    total = ordered[middle - 1] + ordered[middle]
    assert total % 2 == 0
    return total // 2
