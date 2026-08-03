from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


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
