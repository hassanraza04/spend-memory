from typing import Annotated

from fastapi import APIRouter, Depends

from spend_memory.api.contracts import (
    Page,
    SourceEvidenceResponse,
    TransactionFilters,
    TransactionResponse,
    WorkspaceContextResponse,
)
from spend_memory.api.dependencies import get_enrichment_repository
from spend_memory.api.errors import ApiError
from spend_memory.enrichment.models import SearchQuery
from spend_memory.enrichment.repository import EnrichmentRepository
from spend_memory.enrichment.search import SearchRow, search_transactions

router = APIRouter()


@router.get("/workspace-context", response_model=WorkspaceContextResponse)
def get_workspace_context(
    repository: Annotated[EnrichmentRepository, Depends(get_enrichment_repository)],
) -> WorkspaceContextResponse:
    return WorkspaceContextResponse(**repository.workspace_context())


def serialize_transaction(row: SearchRow) -> TransactionResponse:
    transaction = row.transaction
    return TransactionResponse(
        transaction_id=transaction.raw_transaction_id,
        transaction_date=transaction.transaction_date,
        account=transaction.account_identity,
        description=transaction.description,
        currency=transaction.currency,
        amount_minor=transaction.amount_minor,
        direction=transaction.direction,
        merchant=row.merchant_name,
        category=row.category.category_label,
        counterparty=row.counterparty_label,
        state=row.state,
        source=SourceEvidenceResponse(
            document=row.source_document,
            ordinal=row.source_ordinal,
            page=row.source_page,
            row=row.source_row,
            text=row.source_text,
            extraction_confidence=row.extraction_confidence,
        ),
    )


def query_from(filters: TransactionFilters, text: str | None = None) -> SearchQuery:
    return SearchQuery(
        after=filters.after,
        before=filters.before,
        account=filters.account,
        currency=filters.currency,
        direction=filters.direction,
        merchant=filters.merchant,
        category=filters.category,
        counterparty=filters.counterparty,
        amount_min_minor=filters.amount_min_minor,
        amount_max_minor=filters.amount_max_minor,
        state=filters.state,
        text=(filters.query or "").strip() if text is None else text,
    )


def filtered_rows(
    rows: list[SearchRow], query: SearchQuery, *, include_all: bool = False
) -> list[SearchRow]:
    by_id = {row.transaction.raw_transaction_id: row for row in rows}
    return [
        by_id[result.transaction.raw_transaction_id]
        for result in search_transactions(rows, query, include_all=include_all)
    ]


def sorted_rows(rows: list[SearchRow], filters: TransactionFilters) -> list[SearchRow]:
    keys = {
        "date": lambda row: row.transaction.transaction_date,
        "amount": lambda row: row.transaction.amount_minor,
        "merchant": lambda row: row.merchant_name or "",
        "confidence": lambda row: row.extraction_confidence,
    }
    return sorted(
        rows,
        key=lambda row: (keys[filters.sort.value](row), str(row.transaction.raw_transaction_id)),
        reverse=filters.order.value == "desc",
    )


@router.get("/transactions", response_model=Page[TransactionResponse])
def list_transactions(
    filters: Annotated[TransactionFilters, Depends()],
    repository: Annotated[EnrichmentRepository, Depends(get_enrichment_repository)],
) -> Page[TransactionResponse]:
    try:
        rows = repository.list_search_rows()
    except RuntimeError:
        raise ApiError("trusted_records_unavailable", "Trusted records are not ready.", 503) from None
    query = query_from(filters)
    scoped = sorted_rows(filtered_rows(rows, query, include_all=True), filters)
    return Page(
        items=[serialize_transaction(row) for row in scoped[filters.offset : filters.offset + filters.limit]],
        limit=filters.limit,
        offset=filters.offset,
        total=len(scoped),
    )
