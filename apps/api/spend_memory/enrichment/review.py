from __future__ import annotations

from collections import defaultdict
from datetime import date
from statistics import median
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
                        "merchant_key": _merchant_key(first, matches_by_transaction_id),
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
        if transaction.direction == "debit":
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
        first.account_identity == second.account_identity
        and first.currency == second.currency
        and first.direction == second.direction
        and abs((first.transaction_date - second.transaction_date).days) <= 1
        and abs(first.amount_minor) == abs(second.amount_minor)
        and _merchant_key(first, matches_by_transaction_id)
        == _merchant_key(second, matches_by_transaction_id)
    )


def _merchant_key(
    transaction: TrustedTransaction,
    matches_by_transaction_id: dict[UUID, MerchantMatch],
) -> str:
    match = matches_by_transaction_id.get(transaction.raw_transaction_id)
    if (
        match is not None
        and match.status == "confirmed"
        and match.merchant_id is not None
    ):
        return f"merchant:{match.merchant_id}"
    return f"descriptor:{transaction.normalized_description}"


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
    median_amount = median(history)
    mad = median([abs(value - median_amount) for value in history])
    observed_amount = abs(row.amount_minor)
    if mad == 0 or observed_amount <= median_amount + 4 * mad:
        return None
    return UnusualSpendCandidate(
        raw_transaction_id=row.raw_transaction_id,
        confidence=1.0,
        evidence={
            "group_key": f"{account_identity or ''}|{merchant_key}|{currency}",
            "median_amount_minor": int(median_amount),
            "mad_minor": int(mad),
            "observed_amount_minor": observed_amount,
            "sample_size": len(history),
        },
    )
