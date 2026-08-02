from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from uuid import UUID

from spend_memory.enrichment.models import (
    PeriodContribution,
    PeriodExplanation,
    TrustedTransaction,
)

MAX_CONTRIBUTIONS = 3


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
    contribution_total = sum(item.amount_minor for item in contributions)
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
        before_net_amount_minor=before_total,
        after_net_amount_minor=after_total,
        difference_net_amount_minor=difference,
        contribution_total_minor=contribution_total,
        remainder_minor=remainder,
        text=_text(difference, contributions, remainder),
        contributions=tuple(contributions),
        before_raw_transaction_ids=_source_ids(before),
        after_raw_transaction_ids=_source_ids(after),
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
) -> list[PeriodContribution]:
    grouped_rows: dict[tuple[int, str], tuple[list[PeriodRow], list[PeriodRow]]] = (
        defaultdict(lambda: ([], []))
    )
    for index, rows in enumerate((before, after)):
        for row in rows:
            priority, label = _group(row)
            grouped_rows[(priority, label)][index].append(row)
    changes = [
        (
            priority,
            PeriodContribution(
                label=label,
                amount_minor=_net_total(after_rows) - _net_total(before_rows),
                before_raw_transaction_ids=_source_ids(before_rows),
                after_raw_transaction_ids=_source_ids(after_rows),
            ),
        )
        for (priority, label), (before_rows, after_rows) in grouped_rows.items()
        if _net_total(after_rows) != _net_total(before_rows)
    ]
    changes.sort(
        key=lambda change: (
            -abs(change[1].amount_minor),
            change[1].label.casefold(),
            change[1].label,
            change[0],
            change[1].amount_minor,
        )
    )
    return [contribution for _, contribution in changes[:MAX_CONTRIBUTIONS]]


def _group(row: PeriodRow) -> tuple[int, str]:
    if row.recurring_group:
        return 0, row.recurring_group
    if row.merchant_name:
        return 1, row.merchant_name
    if row.category_label:
        return 2, row.category_label
    return 3, row.transaction.normalized_description or row.transaction.description


def _source_ids(rows: list[PeriodRow]) -> tuple[UUID, ...]:
    return tuple(
        row.transaction.raw_transaction_id
        for row in sorted(
            rows,
            key=lambda item: (
                item.transaction.transaction_date,
                str(item.transaction.raw_transaction_id),
            ),
        )
    )


def _text(
    difference: int, contributions: list[PeriodContribution], remainder: int
) -> str:
    if difference == 0:
        return "Spending was unchanged from the previous period."
    direction = "more in" if difference > 0 else "more out"
    sentences = [
        f"Spending was {abs(difference)} minor units {direction} than the previous period."
    ]
    sentences.extend(
        f"{item.label} accounted for {abs(item.amount_minor)} minor units."
        for item in contributions
    )
    if remainder:
        sentences.append(f"Other activity accounted for {abs(remainder)} minor units.")
    return " ".join(sentences)
