from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from spend_memory.api.contracts import (
    CounterpartyAliasRequest,
    CounterpartyAssignmentRequest,
    CounterpartyCreateRequest,
    CounterpartyDetailResponse,
    CounterpartyLensResponse,
    CounterpartyResponse,
    CounterpartyScope,
    CurrencyFlowResponse,
    MutationResponse,
    Page,
    TrendBucketResponse,
)
from spend_memory.api.dependencies import get_enrichment_repository
from spend_memory.api.errors import ApiError
from spend_memory.enrichment.counterparties import (
    summarize_lens,
    summarize_monthly_trend,
)
from spend_memory.enrichment.models import TrustedTransaction
from spend_memory.enrichment.repository import EnrichmentRepository

router = APIRouter()


def _scoped_transactions(
    transactions: list[TrustedTransaction], scope: CounterpartyScope
) -> list[TrustedTransaction]:
    return [
        transaction for transaction in transactions
        if (scope.after is None or transaction.transaction_date >= scope.after)
        and (scope.before is None or transaction.transaction_date < scope.before)
        and (scope.account is None or transaction.account_identity == scope.account)
        and (scope.currency is None or transaction.currency == scope.currency)
        and (scope.direction is None or transaction.direction == scope.direction)
    ]


@router.get("/counterparties", response_model=Page[CounterpartyLensResponse])
def list_counterparties(
    scope: Annotated[CounterpartyScope, Depends()],
    repository: Annotated[EnrichmentRepository, Depends(get_enrichment_repository)],
) -> Page[CounterpartyLensResponse]:
    try:
        items = [
            CounterpartyLensResponse(
                counterparty_id=counterparty.counterparty_id,
                label=counterparty.label,
                lens=tuple(
                    CurrencyFlowResponse(**flow.__dict__)
                    for flow in summarize_lens(_scoped_transactions(
                        repository.list_counterparty_transactions(counterparty.counterparty_id), scope
                    ))
                ),
            )
            for counterparty in repository.list_counterparties()
        ]
    except RuntimeError:
        raise ApiError("trusted_records_unavailable", "Trusted records are not ready.", 503) from None
    return Page(
        items=items[scope.offset : scope.offset + scope.limit],
        limit=scope.limit,
        offset=scope.offset,
        total=len(items),
    )


@router.get("/counterparties/{counterparty_id}/lens", response_model=CounterpartyDetailResponse)
def counterparty_lens(
    counterparty_id: UUID,
    scope: Annotated[CounterpartyScope, Depends()],
    repository: Annotated[EnrichmentRepository, Depends(get_enrichment_repository)],
) -> CounterpartyDetailResponse:
    counterparty = repository.get_counterparty(counterparty_id)
    if counterparty is None:
        raise ApiError("counterparty_not_found", "The counterparty was not found.", 404)
    try:
        transactions = _scoped_transactions(
            repository.list_counterparty_transactions(counterparty_id), scope
        )
    except RuntimeError:
        raise ApiError("trusted_records_unavailable", "Trusted records are not ready.", 503) from None
    return CounterpartyDetailResponse(
        counterparty_id=counterparty.counterparty_id,
        label=counterparty.label,
        lens=tuple(CurrencyFlowResponse(**flow.__dict__) for flow in summarize_lens(transactions)),
        trend=tuple(
            TrendBucketResponse(period_start=bucket.period_start, **bucket.flow.__dict__)
            for bucket in summarize_monthly_trend(transactions)
        ),
    )


@router.post("/counterparties", response_model=CounterpartyResponse, status_code=201)
def create_counterparty(
    request: CounterpartyCreateRequest,
    repository: Annotated[EnrichmentRepository, Depends(get_enrichment_repository)],
) -> CounterpartyResponse:
    try:
        counterparty = repository.create_counterparty(request.label)
    except ValueError:
        raise ApiError("invalid_counterparty", "The counterparty label is not valid.", 422) from None
    return CounterpartyResponse(
        counterparty_id=counterparty.counterparty_id,
        label=counterparty.label,
    )


@router.patch("/counterparties/{counterparty_id}", response_model=MutationResponse)
def confirm_counterparty_alias(
    counterparty_id: UUID,
    request: CounterpartyAliasRequest,
    repository: Annotated[EnrichmentRepository, Depends(get_enrichment_repository)],
) -> MutationResponse:
    if repository.get_counterparty(counterparty_id) is None:
        raise ApiError("counterparty_not_found", "The counterparty was not found.", 404)
    try:
        repository.confirm_counterparty_alias(request.descriptor, counterparty_id)
    except ValueError:
        raise ApiError("invalid_alias", "The descriptor is not valid.", 422) from None
    return MutationResponse()


@router.post(
    "/counterparties/{counterparty_id}/transactions",
    response_model=CounterpartyLensResponse,
)
def assign_transactions(
    counterparty_id: UUID,
    request: CounterpartyAssignmentRequest,
    repository: Annotated[EnrichmentRepository, Depends(get_enrichment_repository)],
) -> CounterpartyLensResponse:
    counterparty = repository.get_counterparty(counterparty_id)
    if counterparty is None:
        raise ApiError("counterparty_not_found", "The counterparty was not found.", 404)
    try:
        repository.assign_counterparty_transactions(counterparty_id, request.transaction_ids)
        lens = summarize_lens(repository.list_counterparty_transactions(counterparty_id))
    except ValueError as error:
        if str(error) == "trusted_transaction_required":
            raise ApiError("untrusted_transaction", "Only trusted transactions can be assigned.", 422) from None
        raise ApiError("assignment_failed", "The assignment could not be completed.", 422) from None
    except RuntimeError:
        raise ApiError("trusted_records_unavailable", "Trusted records are not ready.", 503) from None
    return CounterpartyLensResponse(
        counterparty_id=counterparty.counterparty_id,
        label=counterparty.label,
        lens=tuple(CurrencyFlowResponse(**flow.__dict__) for flow in lens),
    )
