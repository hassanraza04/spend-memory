from typing import Annotated

from fastapi import APIRouter, Depends

from spend_memory.api.contracts import (
    CurrencyFlowResponse,
    TransactionFilters,
    TrendBucketResponse,
    WorkspaceLensResponse,
)
from spend_memory.api.dependencies import get_enrichment_repository
from spend_memory.api.errors import ApiError
from spend_memory.api.routes.transactions import filtered_rows, query_from
from spend_memory.enrichment.counterparties import (
    summarize_lens,
    summarize_monthly_trend,
)
from spend_memory.enrichment.repository import EnrichmentRepository

router = APIRouter()


@router.get("/lens", response_model=WorkspaceLensResponse)
def workspace_lens(
    filters: Annotated[TransactionFilters, Depends()],
    repository: Annotated[EnrichmentRepository, Depends(get_enrichment_repository)],
) -> WorkspaceLensResponse:
    try:
        rows = filtered_rows(
            repository.list_search_rows(), query_from(filters), include_all=True
        )
    except RuntimeError:
        raise ApiError(
            "trusted_records_unavailable", "Trusted records are not ready.", 503
        ) from None
    transactions = [row.transaction for row in rows]
    return WorkspaceLensResponse(
        lens=tuple(CurrencyFlowResponse(**flow.__dict__) for flow in summarize_lens(transactions)),
        trend=tuple(
            TrendBucketResponse(period_start=bucket.period_start, **bucket.flow.__dict__)
            for bucket in summarize_monthly_trend(transactions)
        ),
    )
