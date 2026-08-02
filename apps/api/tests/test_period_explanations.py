from __future__ import annotations

from datetime import date
from uuid import UUID

import pytest
from spend_memory.enrichment.models import TrustedTransaction
from spend_memory.enrichment.periods import (
    PeriodExplanationError,
    PeriodRow,
    explain_period_change,
)


def _row(
    identifier: int,
    period: str,
    amount_minor: int,
    description: str,
    *,
    account_identity: str = "checking",
    currency: str = "AED",
    direction: str = "debit",
    merchant_name: str | None = None,
    category_label: str | None = None,
    recurring_group: str | None = None,
) -> PeriodRow:
    return PeriodRow(
        transaction=TrustedTransaction(
            UUID(int=identifier),
            account_identity,
            date.fromisoformat(f"{period}-01"),
            description,
            description.lower(),
            currency,
            amount_minor,
            direction,
        ),
        merchant_name=merchant_name,
        category_label=category_label,
        recurring_group=recurring_group,
    )


def test_period_explanation_contributions_and_remainder_sum_exactly() -> None:
    explanation = explain_period_change(
        [
            _row(1, "2026-01", 1000, "METRO MART", merchant_name="MetroMart"),
            _row(2, "2026-01", 2999, "STREAMBOX", recurring_group="StreamBox"),
        ],
        [
            _row(3, "2026-02", 1500, "METRO MART", merchant_name="MetroMart"),
            _row(4, "2026-02", 2999, "STREAMBOX", recurring_group="StreamBox"),
            _row(5, "2026-02", 200, "CASH WITHDRAWAL"),
        ],
    )

    assert explanation.before_net_amount_minor == -3999
    assert explanation.after_net_amount_minor == -4699
    assert explanation.difference_net_amount_minor == -700
    assert explanation.contribution_total_minor + explanation.remainder_minor == -700
    assert "700 minor units more out" in explanation.text
    assert "MetroMart accounted for 500 minor units" in explanation.text


def test_period_explanation_uses_group_precedence_without_double_counting() -> None:
    explanation = explain_period_change(
        [
            _row(
                1,
                "2026-01",
                100,
                "STREAMBOX",
                merchant_name="StreamBox",
                category_label="Entertainment",
                recurring_group="StreamBox subscription",
            ),
            _row(2, "2026-01", 300, "METRO MART", merchant_name="MetroMart"),
            _row(3, "2026-01", 400, "FUEL STOP", category_label="Transport"),
        ],
        [
            _row(
                5,
                "2026-02",
                200,
                "STREAMBOX",
                merchant_name="StreamBox",
                category_label="Entertainment",
                recurring_group="StreamBox subscription",
            ),
            _row(6, "2026-02", 500, "METRO MART", merchant_name="MetroMart"),
            _row(7, "2026-02", 600, "FUEL STOP", category_label="Transport"),
        ],
    )

    assert explanation.contribution_total_minor == -500
    assert explanation.remainder_minor == 0
    assert explanation.text.count("StreamBox subscription") == 1
    assert explanation.text.count("MetroMart") == 1
    assert explanation.text.count("Transport") == 1
    assert "StreamBox accounted for" not in explanation.text
    assert "Entertainment accounted for" not in explanation.text


def test_period_explanation_handles_credits_with_integer_minor_units() -> None:
    explanation = explain_period_change(
        [_row(1, "2026-01", 300, "REFUND", direction="credit")],
        [_row(2, "2026-02", 500, "REFUND", direction="credit")],
    )

    assert explanation.before_net_amount_minor == 300
    assert explanation.after_net_amount_minor == 500
    assert explanation.difference_net_amount_minor == 200
    assert explanation.contribution_total_minor + explanation.remainder_minor == 200
    assert "200 minor units more in" in explanation.text


def test_period_explanation_uses_an_unchanged_template_for_zero_difference() -> None:
    explanation = explain_period_change(
        [_row(1, "2026-01", 100, "METRO MART", merchant_name="MetroMart")],
        [_row(2, "2026-02", 100, "METRO MART", merchant_name="MetroMart")],
    )

    assert explanation.difference_net_amount_minor == 0
    assert explanation.contribution_total_minor == 0
    assert explanation.remainder_minor == 0
    assert explanation.text == "Spending was unchanged from the previous period."


def test_period_explanation_limits_contributors_and_reconciles_remainder() -> None:
    before = [
        _row(identifier, "2026-01", 100, label, merchant_name=label)
        for identifier, label in enumerate(("Alpha", "Bravo", "Charlie", "Delta"), 1)
    ]
    after = [
        _row(identifier, "2026-02", amount, label, merchant_name=label)
        for identifier, (label, amount) in enumerate(
            (("Alpha", 500), ("Bravo", 400), ("Charlie", 300), ("Delta", 200)),
            5,
        )
    ]

    explanation = explain_period_change(before, after)

    assert explanation.difference_net_amount_minor == -1000
    assert explanation.contribution_total_minor == -900
    assert explanation.remainder_minor == -100
    assert "Alpha accounted for 400 minor units" in explanation.text
    assert "Bravo accounted for 300 minor units" in explanation.text
    assert "Charlie accounted for 200 minor units" in explanation.text
    assert "Delta accounted for" not in explanation.text
    assert "Other activity accounted for 100 minor units" in explanation.text


def test_period_explanation_rejects_empty_periods_mixed_currency_and_accounts() -> None:
    row = _row(1, "2026-01", 100, "METRO MART")
    with pytest.raises(PeriodExplanationError, match="empty_before"):
        explain_period_change([], [row])
    with pytest.raises(PeriodExplanationError, match="empty_after"):
        explain_period_change([row], [])
    with pytest.raises(PeriodExplanationError, match="mixed_currency"):
        explain_period_change(
            [row], [_row(2, "2026-02", 100, "METRO MART", currency="PKR")]
        )
    with pytest.raises(PeriodExplanationError, match="mixed_account"):
        explain_period_change(
            [row], [_row(2, "2026-02", 100, "METRO MART", account_identity="savings")]
        )
