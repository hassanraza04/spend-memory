from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from spend_memory.enrichment.models import PeriodExplanation, TrustedTransaction


class PeriodExplanationError(ValueError):
    pass


@dataclass(frozen=True)
class PeriodRow:
    """A trusted transaction with labels that are already confirmed locally."""

    transaction: TrustedTransaction
    merchant_name: str | None = None
    category_label: str | None = None
    recurring_group: str | None = None


def explain_period_change(
    before: list[PeriodRow], after: list[PeriodRow]
) -> PeriodExplanation:
    _validate_periods(before, after)
    before_total = _net_total(before)
    after_total = _net_total(after)
    difference = after_total - before_total
    contributions = _contributions(before, after)
    contribution_total = sum(amount for _, amount in contributions)
    remainder = difference - contribution_total
    assert contribution_total + remainder == difference
    assert all(
        isinstance(value, int)
        for value in (
            before_total,
            after_total,
            difference,
            contribution_total,
            remainder,
        )
    )
    return PeriodExplanation(
        before_total,
        after_total,
        difference,
        contribution_total,
        remainder,
        _text(difference, contributions, remainder),
    )


def _validate_periods(before: list[PeriodRow], after: list[PeriodRow]) -> None:
    if not before:
        raise PeriodExplanationError("empty_before")
    if not after:
        raise PeriodExplanationError("empty_after")
    rows = before + after
    currencies = {row.transaction.currency for row in rows}
    accounts = {row.transaction.account_identity for row in rows}
    if len(currencies) != 1:
        raise PeriodExplanationError("mixed_currency")
    if len(accounts) != 1:
        raise PeriodExplanationError("mixed_account")
    for row in rows:
        transaction = row.transaction
        if type(transaction.amount_minor) is not int or transaction.amount_minor < 0:
            raise PeriodExplanationError("invalid_amount_minor")
        if transaction.direction not in {"debit", "credit"}:
            raise PeriodExplanationError("invalid_direction")


def _net_total(rows: list[PeriodRow]) -> int:
    return sum(
        row.transaction.amount_minor
        if row.transaction.direction == "credit"
        else -row.transaction.amount_minor
        for row in rows
    )


def _contributions(
    before: list[PeriodRow], after: list[PeriodRow]
) -> list[tuple[str, int]]:
    totals: dict[tuple[int, str], list[int]] = defaultdict(lambda: [0, 0])
    for index, rows in enumerate((before, after)):
        for row in rows:
            priority, label = _group(row)
            totals[(priority, label)][index] += _net_total([row])
    return sorted(
        (
            (label, totals_after - totals_before)
            for (_, label), (totals_before, totals_after) in totals.items()
            if totals_after != totals_before
        ),
        key=lambda contribution: (-abs(contribution[1]), contribution[0].casefold()),
    )


def _group(row: PeriodRow) -> tuple[int, str]:
    if row.recurring_group:
        return 0, row.recurring_group
    if row.merchant_name:
        return 1, row.merchant_name
    if row.category_label:
        return 2, row.category_label
    return 3, row.transaction.normalized_description or row.transaction.description


def _text(difference: int, contributions: list[tuple[str, int]], remainder: int) -> str:
    direction = "more in" if difference > 0 else "more out"
    sentences = [
        f"Spending was {abs(difference)} minor units {direction} than the previous period."
    ]
    sentences.extend(
        f"{label} accounted for {abs(amount)} minor units."
        for label, amount in contributions
    )
    if remainder:
        sentences.append(f"Other activity accounted for {abs(remainder)} minor units.")
    return " ".join(sentences)
