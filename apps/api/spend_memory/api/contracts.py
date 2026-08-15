from datetime import date
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ErrorDetail(BaseModel):
    field: str
    code: str


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[ErrorDetail] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    error: ErrorBody


class HealthResponse(BaseModel):
    status: str


class Page[Item](BaseModel):
    items: list[Item]
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
    total: int = Field(ge=0)


class PageRequest(BaseModel):
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class TransactionSort(StrEnum):
    date = "date"
    amount = "amount"
    merchant = "merchant"
    confidence = "confidence"


class SortOrder(StrEnum):
    ascending = "asc"
    descending = "desc"


class EntitySort(StrEnum):
    label = "label"
    status = "status"
    confidence = "confidence"


class EntityStatus(StrEnum):
    candidate = "candidate"
    confirmed = "confirmed"
    suggested = "suggested"
    unresolved = "unresolved"


class Direction(StrEnum):
    debit = "debit"
    credit = "credit"


class TransactionQuery(PageRequest):
    sort: TransactionSort = TransactionSort.date
    order: SortOrder = SortOrder.descending


class EntityQuery(PageRequest):
    sort: EntitySort = EntitySort.label
    order: SortOrder = SortOrder.ascending
    status: EntityStatus | None = None
    after: date | None = None
    before: date | None = None
    account: str | None = None
    currency: str | None = Field(default=None, min_length=1, max_length=12)
    direction: Direction | None = None
    query: str | None = None

    @model_validator(mode="after")
    def validate_date_range(self) -> "EntityQuery":
        if self.after is not None and self.before is not None and self.after >= self.before:
            raise ValueError("after_must_precede_before")
        return self


class CategoryQuery(EntityQuery):
    pass


class TransactionPath(BaseModel):
    transaction_id: UUID


class SourceEvidenceResponse(BaseModel):
    document: str
    ordinal: int
    page: int | None
    row: int | None
    text: str
    extraction_confidence: float


class TransactionResponse(BaseModel):
    transaction_id: UUID
    transaction_date: date
    account: str | None
    description: str
    currency: str
    amount_minor: int
    direction: Direction
    merchant: str | None
    category: str
    counterparty: str | None
    state: str
    source: SourceEvidenceResponse


class TransactionFilters(TransactionQuery):
    after: date | None = None
    before: date | None = None
    account: str | None = None
    currency: str | None = None
    direction: Direction | None = None
    amount_min_minor: int | None = Field(default=None, ge=0)
    amount_max_minor: int | None = Field(default=None, ge=0)
    merchant: str | None = None
    category: str | None = None
    counterparty: str | None = None
    state: str | None = None

    @model_validator(mode="after")
    def validate_ranges(self) -> "TransactionFilters":
        if self.after is not None and self.before is not None and self.after >= self.before:
            raise ValueError("after_must_precede_before")
        if (
            self.amount_min_minor is not None
            and self.amount_max_minor is not None
            and self.amount_min_minor > self.amount_max_minor
        ):
            raise ValueError("amount_min_must_not_exceed_max")
        return self


class CurrencyFlowResponse(BaseModel):
    currency: str
    sent_minor: int
    received_minor: int
    net_minor: int
    transaction_count: int


class TrendBucketResponse(CurrencyFlowResponse):
    period_start: date


class WorkspaceLensResponse(BaseModel):
    lens: tuple[CurrencyFlowResponse, ...]
    trend: tuple[TrendBucketResponse, ...]


class WorkspaceAccountResponse(BaseModel):
    account: str
    currencies: tuple[str, ...]


class WorkspaceContextResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    first_transaction_date: date | None = Field(alias="firstTransactionDate")
    last_transaction_date: date | None = Field(alias="lastTransactionDate")
    latest_month_start: date | None = Field(alias="latestMonthStart")
    latest_month_end: date | None = Field(alias="latestMonthEnd")
    accounts: tuple[WorkspaceAccountResponse, ...]


class SearchResponse(BaseModel):
    query: str
    items: list[TransactionResponse]
    lens: tuple[CurrencyFlowResponse, ...]


class ImportResponse(BaseModel):
    document_id: UUID
    run_id: UUID
    transaction_count: int
    was_already_imported: bool
    parser_id: str
    parser_version: str


class ImportInspectionResponse(BaseModel):
    document_id: UUID
    run_id: UUID
    original_filename: str
    mime_type: str
    byte_size: int
    transaction_count: int
    parser_id: str
    parser_version: str
    is_demo: bool


class CounterpartyAssignmentRequest(BaseModel):
    transaction_ids: list[UUID] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def reject_duplicate_transactions(self) -> "CounterpartyAssignmentRequest":
        if len(set(self.transaction_ids)) != len(self.transaction_ids):
            raise ValueError("duplicate_transaction_ids")
        return self


class CounterpartyScope(PageRequest):
    after: date | None = None
    before: date | None = None
    account: str | None = None
    currency: str | None = Field(default=None, min_length=1, max_length=12)
    direction: Direction | None = None

    @model_validator(mode="after")
    def validate_date_range(self) -> "CounterpartyScope":
        if self.after is not None and self.before is not None and self.after >= self.before:
            raise ValueError("after_must_precede_before")
        return self


class CounterpartyLensResponse(BaseModel):
    counterparty_id: UUID
    label: str
    lens: tuple[CurrencyFlowResponse, ...]


class CounterpartyResponse(BaseModel):
    counterparty_id: UUID
    label: str


class CounterpartyDetailResponse(CounterpartyLensResponse):
    trend: tuple[TrendBucketResponse, ...]


class CounterpartyCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=200)

    @field_validator("label")
    @classmethod
    def strip_label(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("label_required")
        return value


class CounterpartyAliasRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    descriptor: str = Field(min_length=1, max_length=500)

    @field_validator("descriptor")
    @classmethod
    def strip_descriptor(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("descriptor_required")
        return value


class MerchantEvidenceResponse(BaseModel):
    transaction_id: UUID
    merchant_id: UUID | None
    merchant_name: str | None
    status: str
    confidence: float = Field(ge=0, le=1)
    method: str
    evidence: dict[str, str | int | float]


class CategoryResponse(BaseModel):
    category_id: UUID
    label: str
    lens: tuple[CurrencyFlowResponse, ...]


class PeoplePlaceResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    key: str
    label: str
    kind: Literal["person", "place", "unresolved"]
    status: Literal["confirmed", "unresolved"]
    transaction_count: int = Field(alias="transactionCount", ge=1)
    last_activity_date: date = Field(alias="lastActivityDate")
    flows: tuple[CurrencyFlowResponse, ...]
    recent_transaction_ids: tuple[UUID, ...] = Field(alias="recentTransactionIds")


class RecurringCandidateResponse(BaseModel):
    candidate_id: UUID
    label: str
    cadence: str
    status: str
    confidence: float = Field(ge=0, le=1)
    evidence: dict[str, str | int | float]
    transaction_ids: tuple[UUID, ...]
    expected_next_start: date
    expected_next_end: date


class ReviewCandidateResponse(BaseModel):
    candidate_id: UUID
    kind: Literal["duplicate", "unusual_spend"]
    status: str
    confidence: float = Field(ge=0, le=1)
    evidence: dict[str, str | int | float]
    transaction_ids: tuple[UUID, ...]


class MerchantCorrectionRequest(BaseModel):
    descriptor: str | None = Field(default=None, min_length=1, max_length=500)
    category_id: UUID | None = None

    @model_validator(mode="after")
    def requires_a_change(self) -> "MerchantCorrectionRequest":
        if self.descriptor is None and self.category_id is None:
            raise ValueError("merchant_correction_required")
        return self


class TransactionCorrectionRequest(BaseModel):
    category_id: UUID


class MutationResponse(BaseModel):
    status: Literal["saved"] = "saved"


class ComparisonQuery(BaseModel):
    before_start: date
    before_end: date
    after_start: date
    after_end: date
    account: str = Field(min_length=1, max_length=500)
    currency: str = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def requires_non_overlapping_ranges(self) -> "ComparisonQuery":
        if self.before_start >= self.before_end or self.after_start >= self.after_end:
            raise ValueError("invalid_period_range")
        if self.before_start < self.after_end and self.after_start < self.before_end:
            raise ValueError("overlapping_period_ranges")
        return self


class PeriodContributionResponse(BaseModel):
    label: str
    amount_minor: int
    before_transaction_ids: tuple[UUID, ...]
    after_transaction_ids: tuple[UUID, ...]


class PeriodExplanationResponse(BaseModel):
    before_net_amount_minor: int
    after_net_amount_minor: int
    difference_net_amount_minor: int
    contribution_total_minor: int
    remainder_minor: int
    text: str
    contributions: tuple[PeriodContributionResponse, ...]
    before_transaction_ids: tuple[UUID, ...]
    after_transaction_ids: tuple[UUID, ...]


class LocalDataConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmation: Literal["DELETE LOCAL DATA"]


class LocalDataResponse(BaseModel):
    status: Literal["deleted", "reset"]
