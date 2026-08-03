from datetime import date
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


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


class TransactionQuery(PageRequest):
    sort: TransactionSort = TransactionSort.date
    order: SortOrder = SortOrder.descending


class TransactionPath(BaseModel):
    transaction_id: UUID


class Direction(StrEnum):
    debit = "debit"
    credit = "credit"


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


class SearchResponse(BaseModel):
    query: str
    items: list[TransactionResponse]
    lens: tuple[CurrencyFlowResponse, ...]


class ImportResponse(BaseModel):
    document_id: UUID
    run_id: UUID
    transaction_count: int
    was_already_imported: bool


class CounterpartyAssignmentRequest(BaseModel):
    transaction_ids: list[UUID] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def reject_duplicate_transactions(self) -> "CounterpartyAssignmentRequest":
        if len(set(self.transaction_ids)) != len(self.transaction_ids):
            raise ValueError("duplicate_transaction_ids")
        return self


class CounterpartyLensResponse(BaseModel):
    counterparty_id: UUID
    label: str
    lens: tuple[CurrencyFlowResponse, ...]
