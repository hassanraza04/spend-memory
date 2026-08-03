from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from spend_memory.api.contracts import (
    CounterpartyAssignmentRequest,
    CounterpartyLensResponse,
    CurrencyFlowResponse,
)
from spend_memory.api.dependencies import get_enrichment_repository
from spend_memory.api.errors import ApiError
from spend_memory.enrichment.counterparties import summarize_lens
from spend_memory.enrichment.repository import EnrichmentRepository

router = APIRouter()


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
