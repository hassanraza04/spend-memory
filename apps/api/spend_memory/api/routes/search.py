from typing import Annotated

from fastapi import APIRouter, Depends, Query

from spend_memory.api.contracts import (
    CurrencyFlowResponse,
    SearchResponse,
    TransactionFilters,
)
from spend_memory.api.dependencies import get_enrichment_repository
from spend_memory.api.errors import ApiError
from spend_memory.api.routes.transactions import (
    filtered_rows,
    query_from,
    serialize_transaction,
)
from spend_memory.enrichment.counterparties import summarize_lens
from spend_memory.enrichment.repository import EnrichmentRepository

router = APIRouter()


@router.get("/search", response_model=SearchResponse)
def search_transactions_route(
    filters: Annotated[TransactionFilters, Depends()],
    repository: Annotated[EnrichmentRepository, Depends(get_enrichment_repository)],
    query: Annotated[str, Query()] = "",
) -> SearchResponse:
    if not query and filters.account is None and filters.counterparty is None:
        raise ApiError(
            "invalid_filter",
            "Provide a search query or an account or counterparty filter.",
            422,
        )
    try:
        scoped = filtered_rows(
            repository.list_search_rows(),
            query_from(filters, query),
            include_all=not query,
        )
    except RuntimeError:
        raise ApiError("trusted_records_unavailable", "Trusted records are not ready.", 503) from None
    lens = summarize_lens(row.transaction for row in scoped)
    page = scoped[filters.offset : filters.offset + filters.limit]
    return SearchResponse(
        query=query,
        items=[serialize_transaction(row) for row in page],
        lens=tuple(CurrencyFlowResponse(**flow.__dict__) for flow in lens),
    )
