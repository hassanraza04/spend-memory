from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import ValidationError

from spend_memory.api.contracts import (
    ComparisonQuery,
    PeriodContributionResponse,
    PeriodExplanationResponse,
)
from spend_memory.api.dependencies import get_enrichment_repository
from spend_memory.api.errors import ApiError
from spend_memory.enrichment.periods import (
    PeriodExplanationError,
    explain_period_change,
)
from spend_memory.enrichment.repository import EnrichmentRepository

router = APIRouter()


def comparison_query(
    before_start: Annotated[date, Query()],
    before_end: Annotated[date, Query()],
    after_start: Annotated[date, Query()],
    after_end: Annotated[date, Query()],
    account: Annotated[str, Query(min_length=1, max_length=500)],
    currency: Annotated[str, Query(min_length=1, max_length=12)],
) -> ComparisonQuery:
    try:
        return ComparisonQuery(
            before_start=before_start,
            before_end=before_end,
            after_start=after_start,
            after_end=after_end,
            account=account,
            currency=currency,
        )
    except ValidationError:
        raise ApiError("invalid_filter", "The comparison periods are not valid.", 422) from None


@router.get("/comparisons", response_model=PeriodExplanationResponse)
def compare_periods(
    query: Annotated[ComparisonQuery, Depends(comparison_query)],
    repository: Annotated[EnrichmentRepository, Depends(get_enrichment_repository)],
) -> PeriodExplanationResponse:
    try:
        explanation = explain_period_change(
            repository.list_period_rows(query.before_start, query.before_end, query.account, query.currency),
            repository.list_period_rows(query.after_start, query.after_end, query.account, query.currency),
        )
    except RuntimeError:
        raise ApiError("trusted_records_unavailable", "Trusted records are not ready.", 503) from None
    except PeriodExplanationError:
        raise ApiError("comparison_unavailable", "The selected periods cannot be compared.", 422) from None
    return PeriodExplanationResponse(
        before_net_amount_minor=explanation.before_net_amount_minor,
        after_net_amount_minor=explanation.after_net_amount_minor,
        difference_net_amount_minor=explanation.difference_net_amount_minor,
        contribution_total_minor=explanation.contribution_total_minor,
        remainder_minor=explanation.remainder_minor,
        text=explanation.text,
        contributions=tuple(
            PeriodContributionResponse(
                label=item.label,
                amount_minor=item.amount_minor,
                before_transaction_ids=item.before_raw_transaction_ids,
                after_transaction_ids=item.after_raw_transaction_ids,
            )
            for item in explanation.contributions
        ),
        before_transaction_ids=explanation.before_raw_transaction_ids,
        after_transaction_ids=explanation.after_raw_transaction_ids,
    )
