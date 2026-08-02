from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from hashlib import sha256
from uuid import UUID

from spend_memory.enrichment.models import MerchantMatch, RecurringCandidate, TrustedTransaction

CADENCES = {
    "weekly": (5, 9),
    "monthly": (26, 35),
    "quarterly": (80, 100),
    "annual": (350, 380),
}

EXPECTED_WINDOWS = {"monthly": (28, 34)}


def detect_recurring_candidates(
    transactions: list[TrustedTransaction],
    matches_by_transaction_id: dict[UUID, MerchantMatch],
) -> list[RecurringCandidate]:
    groups: dict[tuple[str | None, UUID | str, str], list[TrustedTransaction]] = defaultdict(list)
    for transaction in transactions:
        if transaction.direction != "debit":
            continue
        match = matches_by_transaction_id.get(transaction.raw_transaction_id)
        merchant = (
            match.merchant_id
            if match is not None and match.status == "confirmed" and match.merchant_id is not None
            else transaction.normalized_description
        )
        groups[(transaction.account_identity, merchant, transaction.currency)].append(transaction)

    candidates: list[RecurringCandidate] = []
    for (account_identity, merchant, currency), rows in groups.items():
        rows.sort(key=lambda row: (row.transaction_date, str(row.raw_transaction_id)))
        if len(rows) < 3:
            continue
        amounts = [abs(row.amount_minor) for row in rows]
        intervals = [
            (later.transaction_date - earlier.transaction_date).days
            for earlier, later in zip(rows, rows[1:])
        ]
        cadence = next(
            (
                name
                for name, (minimum, maximum) in CADENCES.items()
                if all(minimum <= interval <= maximum for interval in intervals)
            ),
            None,
        )
        if cadence is None or not _amounts_are_consistent(amounts):
            continue
        minimum, maximum = EXPECTED_WINDOWS.get(cadence, CADENCES[cadence])
        merchant_id = merchant if isinstance(merchant, UUID) else None
        normalized_descriptor = (
            min(row.normalized_description for row in rows)
            if merchant_id is not None
            else merchant
        )
        key_parts = (account_identity or "", str(merchant), currency, cadence)
        candidate_key = sha256("\x1f".join(key_parts).encode()).hexdigest()
        candidates.append(
            RecurringCandidate(
                candidate_key=candidate_key,
                account_identity=account_identity,
                merchant_id=merchant_id,
                normalized_descriptor=normalized_descriptor,
                currency=currency,
                direction="debit",
                cadence=cadence,
                first_transaction_date=rows[0].transaction_date,
                last_transaction_date=rows[-1].transaction_date,
                amount_min_minor=min(amounts),
                amount_max_minor=max(amounts),
                expected_next_start=rows[-1].transaction_date + timedelta(days=minimum),
                expected_next_end=rows[-1].transaction_date + timedelta(days=maximum),
                confidence=1.0,
                evidence={
                    "transaction_dates": ",".join(
                        row.transaction_date.isoformat() for row in rows
                    ),
                    "interval_days": ",".join(str(interval) for interval in intervals),
                    "observation_count": len(rows),
                    "amount_tolerance_minor": max(1, round(max(amounts) * 0.1)),
                },
            )
        )
    return sorted(candidates, key=lambda candidate: candidate.candidate_key)


def _amounts_are_consistent(values: list[int]) -> bool:
    return max(values) - min(values) <= max(1, round(max(values) * 0.1))
