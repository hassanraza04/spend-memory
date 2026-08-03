from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID


@dataclass(frozen=True)
class TrustedTransaction:
    raw_transaction_id: UUID
    account_identity: str | None
    transaction_date: date
    description: str
    normalized_description: str
    currency: str
    amount_minor: int
    direction: str


@dataclass(frozen=True)
class MerchantMatch:
    merchant_id: UUID | None
    merchant_name: str | None
    status: str
    confidence: float
    method: str
    evidence: dict[str, str | float]


@dataclass(frozen=True)
class CategoryDecision:
    category_id: UUID | None
    category_label: str
    source: str


@dataclass(frozen=True)
class SearchResult:
    transaction: TrustedTransaction
    score: float


@dataclass(frozen=True)
class PeriodContribution:
    label: str
    amount_minor: int
    before_raw_transaction_ids: tuple[UUID, ...]
    after_raw_transaction_ids: tuple[UUID, ...]


@dataclass(frozen=True)
class PeriodExplanation:
    before_net_amount_minor: int
    after_net_amount_minor: int
    difference_net_amount_minor: int
    contribution_total_minor: int
    remainder_minor: int
    text: str
    contributions: tuple[PeriodContribution, ...]
    before_raw_transaction_ids: tuple[UUID, ...]
    after_raw_transaction_ids: tuple[UUID, ...]


@dataclass(frozen=True)
class RecurringCandidate:
    candidate_key: str
    account_identity: str | None
    merchant_id: UUID | None
    normalized_descriptor: str
    currency: str
    direction: str
    cadence: str
    first_transaction_date: date
    last_transaction_date: date
    amount_min_minor: int
    amount_max_minor: int
    expected_next_start: date
    expected_next_end: date
    raw_transaction_ids: tuple[UUID, ...]
    confidence: float
    evidence: dict[str, str | int | float]


@dataclass(frozen=True)
class DuplicateCandidate:
    raw_transaction_ids: tuple[UUID, UUID]
    confidence: float
    evidence: dict[str, str | int | float]


@dataclass(frozen=True)
class UnusualSpendCandidate:
    raw_transaction_id: UUID
    confidence: float
    evidence: dict[str, str | int | float]


@dataclass(frozen=True)
class SearchQuery:
    after: date | None = None
    before: date | None = None
    currency: str | None = None
    direction: str | None = None
    merchant: str | None = None
    category: str | None = None
    amount_min_minor: int | None = None
    amount_max_minor: int | None = None
    state: str | None = None
    text: str = ""


@dataclass(frozen=True)
class MerchantEvaluation:
    precision: float
    recall: float
    coverage: float
    expected_calibration_error: float
    baseline_precision: float
    baseline_recall: float
    baseline_coverage: float
    baseline_expected_calibration_error: float


@dataclass(frozen=True)
class Merchant:
    merchant_id: UUID
    merchant_name: str


@dataclass(frozen=True)
class Category:
    category_id: UUID
    category_label: str


@dataclass(frozen=True)
class Counterparty:
    counterparty_id: UUID
    label: str


@dataclass(frozen=True)
class CurrencyFlow:
    currency: str
    sent_minor: int
    received_minor: int
    net_minor: int
    transaction_count: int
