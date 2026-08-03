from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from spend_memory.api.contracts import (
    CategoryResponse,
    MerchantCorrectionRequest,
    MerchantEvidenceResponse,
    MutationResponse,
    Page,
    PageRequest,
    RecurringCandidateResponse,
    ReviewCandidateResponse,
    TransactionCorrectionRequest,
)
from spend_memory.api.dependencies import get_enrichment_repository
from spend_memory.api.errors import ApiError
from spend_memory.enrichment.repository import EnrichmentRepository

router = APIRouter()


def _page(items: list[object], request: PageRequest) -> Page[object]:
    return Page(
        items=items[request.offset : request.offset + request.limit],
        limit=request.limit,
        offset=request.offset,
        total=len(items),
    )


@router.get("/merchants", response_model=Page[MerchantEvidenceResponse])
def list_merchants(
    request: Annotated[PageRequest, Depends()],
    repository: Annotated[EnrichmentRepository, Depends(get_enrichment_repository)],
) -> Page[MerchantEvidenceResponse]:
    try:
        return _page(
            [MerchantEvidenceResponse(**item.__dict__) for item in repository.list_merchant_evidence()],
            request,
        )
    except RuntimeError:
        raise ApiError("trusted_records_unavailable", "Trusted records are not ready.", 503) from None


@router.get("/categories", response_model=Page[CategoryResponse])
def list_categories(
    request: Annotated[PageRequest, Depends()],
    repository: Annotated[EnrichmentRepository, Depends(get_enrichment_repository)],
) -> Page[CategoryResponse]:
    return _page(
        [CategoryResponse(category_id=item.category_id, label=item.category_label) for item in repository.list_categories()],
        request,
    )


@router.get("/recurring", response_model=Page[RecurringCandidateResponse])
def list_recurring(
    request: Annotated[PageRequest, Depends()],
    repository: Annotated[EnrichmentRepository, Depends(get_enrichment_repository)],
) -> Page[RecurringCandidateResponse]:
    try:
        return _page(
            [RecurringCandidateResponse(**item.__dict__) for item in repository.list_recurring_evidence()],
            request,
        )
    except RuntimeError:
        raise ApiError("trusted_records_unavailable", "Trusted records are not ready.", 503) from None


@router.get("/review", response_model=Page[ReviewCandidateResponse])
def list_review(
    request: Annotated[PageRequest, Depends()],
    repository: Annotated[EnrichmentRepository, Depends(get_enrichment_repository)],
) -> Page[ReviewCandidateResponse]:
    try:
        return _page(
            [ReviewCandidateResponse(**item.__dict__) for item in repository.list_review_evidence()],
            request,
        )
    except RuntimeError:
        raise ApiError("trusted_records_unavailable", "Trusted records are not ready.", 503) from None


@router.patch("/merchants/{merchant_id}", response_model=MutationResponse)
def correct_merchant(
    merchant_id: UUID,
    correction: MerchantCorrectionRequest,
    repository: Annotated[EnrichmentRepository, Depends(get_enrichment_repository)],
) -> MutationResponse:
    if repository.get_merchant(merchant_id) is None:
        raise ApiError("merchant_not_found", "The merchant was not found.", 404)
    if correction.category_id is not None and repository.get_category(correction.category_id) is None:
        raise ApiError("category_not_found", "The category was not found.", 404)
    if correction.descriptor is not None:
        repository.confirm_alias(correction.descriptor, merchant_id)
    if correction.category_id is not None:
        repository.assign_merchant_category(merchant_id, correction.category_id)
    return MutationResponse()


@router.patch("/transactions/{transaction_id}", response_model=MutationResponse)
def correct_transaction_category(
    transaction_id: UUID,
    correction: TransactionCorrectionRequest,
    repository: Annotated[EnrichmentRepository, Depends(get_enrichment_repository)],
) -> MutationResponse:
    if repository.get_category(correction.category_id) is None:
        raise ApiError("category_not_found", "The category was not found.", 404)
    try:
        repository.set_trusted_transaction_category_override(transaction_id, correction.category_id)
    except ValueError:
        raise ApiError("untrusted_transaction", "The transaction is not in trusted records.", 422) from None
    return MutationResponse()
