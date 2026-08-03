from __future__ import annotations

from collections.abc import Iterable

from spend_memory.enrichment.models import CurrencyFlow, TrustedTransaction


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
