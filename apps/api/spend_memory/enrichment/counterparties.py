from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from spend_memory.enrichment.models import CurrencyFlow, TrustedTransaction


@dataclass(frozen=True)
class CurrencyFlowBucket:
    period_start: date
    flow: CurrencyFlow


def summarize_lens(transactions: Iterable[TrustedTransaction]) -> tuple[CurrencyFlow, ...]:
    totals: dict[str, list[int]] = {}
    for transaction in transactions:
        sent_minor, received_minor, transaction_count = totals.setdefault(
            transaction.currency, [0, 0, 0]
        )
        if transaction.direction == "debit":
            sent_minor += transaction.amount_minor
        elif transaction.direction == "credit":
            received_minor += transaction.amount_minor
        else:
            raise ValueError("invalid_direction")
        totals[transaction.currency] = [sent_minor, received_minor, transaction_count + 1]
    return tuple(
        CurrencyFlow(
            currency,
            sent_minor,
            received_minor,
            received_minor - sent_minor,
            transaction_count,
        )
        for currency, (sent_minor, received_minor, transaction_count) in sorted(
            totals.items()
        )
    )


def summarize_monthly_trend(
    transactions: Iterable[TrustedTransaction],
) -> tuple[CurrencyFlowBucket, ...]:
    buckets: dict[date, list[TrustedTransaction]] = {}
    for transaction in transactions:
        period_start = transaction.transaction_date.replace(day=1)
        buckets.setdefault(period_start, []).append(transaction)
    return tuple(
        CurrencyFlowBucket(period_start, flow)
        for period_start, rows in sorted(buckets.items())
        for flow in summarize_lens(rows)
    )
