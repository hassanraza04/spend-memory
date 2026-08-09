from __future__ import annotations

from datetime import date
from uuid import UUID

from spend_memory.enrichment.counterparties import summarize_lens
from spend_memory.enrichment.models import CurrencyFlow, TrustedTransaction


def _transaction(
    identifier: int, currency: str, amount_minor: int, direction: str
) -> TrustedTransaction:
    return TrustedTransaction(
        UUID(int=identifier),
        "synthetic",
        date(2026, 1, identifier),
        f"Synthetic {identifier}",
        f"synthetic {identifier}",
        currency,
        amount_minor,
        direction,
    )


def test_lens_separates_currency_and_debit_from_credit() -> None:
    summary = summarize_lens(
        [
            _transaction(1, "AED", 1200, "debit"),
            _transaction(2, "AED", 200, "credit"),
            _transaction(3, "PKR", 5000, "debit"),
            _transaction(4, "PKR", 7500, "credit"),
        ]
    )

    assert summary == (
        CurrencyFlow("AED", sent_minor=1200, received_minor=200, net_minor=-1000, transaction_count=2),
        CurrencyFlow("PKR", sent_minor=5000, received_minor=7500, net_minor=2500, transaction_count=2),
    )
