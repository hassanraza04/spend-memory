from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from spend_memory.api.contracts import (
    CategoryQuery,
    CategoryResponse,
    CurrencyFlowResponse,
    EntityQuery,
    MerchantCorrectionRequest,
    MerchantEvidenceResponse,
    MutationResponse,
    Page,
    PeoplePlaceResponse,
    RecurringCandidateResponse,
    ReviewCandidateResponse,
    TransactionCorrectionRequest,
)
from spend_memory.api.dependencies import (
    get_enrichment_repository,
    get_local_workspace_refresh,
)
from spend_memory.api.errors import ApiError
from spend_memory.api.routes.transactions import filtered_rows
from spend_memory.enrichment.counterparties import summarize_lens
from spend_memory.enrichment.models import SearchQuery
from spend_memory.enrichment.repository import EnrichmentRepository
from spend_memory.enrichment.search import SearchRow
from spend_memory.local_refresh import LocalRefreshError, LocalWorkspaceRefresh

router = APIRouter()


def _page(items: list[object], request: EntityQuery) -> Page[object]:
    return Page(
        items=items[request.offset : request.offset + request.limit],
        limit=request.limit,
        offset=request.offset,
        total=len(items),
    )


def _ordered(items: list[object], request: EntityQuery) -> list[object]:
    if request.status is not None:
        items = [item for item in items if getattr(item, "status", None) == request.status]
    key = {
        "label": lambda item: str(
            getattr(item, "label", getattr(item, "merchant_name", ""))
        ).casefold(),
        "status": lambda item: str(getattr(item, "status", "")),
        "confidence": lambda item: float(getattr(item, "confidence", 0)),
    }[request.sort.value]
    return sorted(items, key=key, reverse=request.order.value == "desc")


def _has_scope(request: EntityQuery, *, include_currency: bool = True) -> bool:
    return any(
        value is not None
        for value in (
            request.after,
            request.before,
            request.account,
            request.currency if include_currency else None,
            request.direction,
            request.amount_min_minor,
            request.amount_max_minor,
            request.merchant,
            request.category,
            request.counterparty,
            request.state,
            request.query,
        )
    )


def _scoped_rows(
    repository: EnrichmentRepository, request: EntityQuery
) -> list[SearchRow]:
    text = (request.query or "").strip()
    return filtered_rows(
        repository.list_search_rows(),
        SearchQuery(
            after=request.after,
            before=request.before,
            account=request.account,
            currency=request.currency,
            direction=request.direction,
            merchant=request.merchant,
            category=request.category,
            counterparty=request.counterparty,
            amount_min_minor=request.amount_min_minor,
            amount_max_minor=request.amount_max_minor,
            state=request.state,
            text=text,
        ),
        include_all=not text,
    )


def _people_places(
    rows: list[SearchRow],
    merchant_ids: dict[UUID, UUID],
    counterparty_ids: dict[UUID, UUID],
) -> list[PeoplePlaceResponse]:
    groups: dict[tuple[str, str], tuple[str, str, list[SearchRow]]] = {}
    for row in rows:
        transaction_id = row.transaction.raw_transaction_id
        if row.counterparty_label and transaction_id in counterparty_ids:
            identity = ("person", str(counterparty_ids[transaction_id]))
            label, status = row.counterparty_label, "confirmed"
        elif (
            row.state == "confirmed"
            and row.merchant_name
            and transaction_id in merchant_ids
        ):
            identity = ("place", str(merchant_ids[transaction_id]))
            label, status = row.merchant_name, "confirmed"
        else:
            identity = ("unresolved", row.transaction.normalized_description)
            label, status = "Unresolved statement label", "unresolved"
        groups.setdefault(identity, (label, status, []))[2].append(row)

    items = []
    for (kind, identity), (label, status, group_rows) in groups.items():
        recent = sorted(
            group_rows,
            key=lambda row: (
                row.transaction.transaction_date,
                str(row.transaction.raw_transaction_id),
            ),
            reverse=True,
        )
        key_identity = (
            str(recent[-1].transaction.raw_transaction_id)
            if kind == "unresolved"
            else identity
        )
        key_prefix = {"person": "counterparty", "place": "merchant"}.get(kind, kind)
        items.append(PeoplePlaceResponse(
            key=f"{key_prefix}:{key_identity}",
            label=label,
            kind=kind,
            status=status,
            transaction_count=len(group_rows),
            last_activity_date=recent[0].transaction.transaction_date,
            flows=tuple(
                CurrencyFlowResponse(**flow.__dict__)
                for flow in summarize_lens(row.transaction for row in group_rows)
            ),
            recent_transaction_ids=tuple(
                row.transaction.raw_transaction_id for row in recent
            ),
        ))
    return sorted(items, key=lambda item: (item.label.casefold(), item.key))


@router.get("/merchants", response_model=Page[MerchantEvidenceResponse])
def list_merchants(
    request: Annotated[EntityQuery, Depends()],
    repository: Annotated[EnrichmentRepository, Depends(get_enrichment_repository)],
) -> Page[MerchantEvidenceResponse]:
    try:
        items = repository.list_merchant_evidence()
        if request.after is not None:
            items = [item for item in items if item.transaction_date >= request.after]
        if request.before is not None:
            items = [item for item in items if item.transaction_date < request.before]
        if any(
            value is not None
            for value in (request.account, request.currency, request.direction, request.query)
        ):
            scoped_ids = {
                row.transaction.raw_transaction_id
                for row in _scoped_rows(repository, request)
            }
            items = [item for item in items if item.transaction_id in scoped_ids]
        return _page(_ordered([
            MerchantEvidenceResponse(**item.__dict__) for item in items
        ], request), request)
    except RuntimeError:
        raise ApiError("trusted_records_unavailable", "Trusted records are not ready.", 503) from None


@router.get("/categories", response_model=Page[CategoryResponse])
def list_categories(
    request: Annotated[CategoryQuery, Depends()],
    repository: Annotated[EnrichmentRepository, Depends(get_enrichment_repository)],
) -> Page[CategoryResponse]:
    try:
        if _has_scope(request, include_currency=False):
            rows = _scoped_rows(repository, request)
            by_category: dict[UUID, list[SearchRow]] = {}
            for row in rows:
                if row.category.category_id is not None:
                    by_category.setdefault(row.category.category_id, []).append(row)
            items = [
                CategoryResponse(
                    category_id=category_id,
                    label=category_rows[0].category.category_label,
                    lens=tuple(
                        CurrencyFlowResponse(**flow.__dict__)
                        for flow in summarize_lens(
                            row.transaction for row in category_rows
                        )
                    ),
                )
                for category_id, category_rows in by_category.items()
            ]
            return _page(_ordered(items, request), request)
        return _page(_ordered([
            CategoryResponse(
                category_id=item.category.category_id,
                label=item.category.category_label,
                lens=tuple(CurrencyFlowResponse(**flow.__dict__) for flow in item.lens),
            )
            for item in repository.list_category_summaries(request.currency)
        ], request), request)
    except RuntimeError:
        raise ApiError("trusted_records_unavailable", "Trusted records are not ready.", 503) from None


@router.get("/recurring", response_model=Page[RecurringCandidateResponse])
def list_recurring(
    request: Annotated[EntityQuery, Depends()],
    repository: Annotated[EnrichmentRepository, Depends(get_enrichment_repository)],
) -> Page[RecurringCandidateResponse]:
    try:
        evidence = repository.list_recurring_evidence()
        if _has_scope(request):
            scoped_ids = {
                row.transaction.raw_transaction_id
                for row in _scoped_rows(repository, request)
            }
            evidence = [
                item for item in evidence
                if item.transaction_ids and set(item.transaction_ids) <= scoped_ids
            ]
        return _page(_ordered([
            RecurringCandidateResponse(**item.__dict__) for item in evidence
        ], request), request)
    except RuntimeError:
        raise ApiError("trusted_records_unavailable", "Trusted records are not ready.", 503) from None


@router.get("/review", response_model=Page[ReviewCandidateResponse])
def list_review(
    request: Annotated[EntityQuery, Depends()],
    repository: Annotated[EnrichmentRepository, Depends(get_enrichment_repository)],
) -> Page[ReviewCandidateResponse]:
    try:
        evidence = repository.list_review_evidence()
        if _has_scope(request):
            scoped_ids = {
                row.transaction.raw_transaction_id
                for row in _scoped_rows(repository, request)
            }
            evidence = [
                item for item in evidence
                if item.transaction_ids and set(item.transaction_ids) <= scoped_ids
            ]
        return _page(_ordered([
            ReviewCandidateResponse(**item.__dict__) for item in evidence
        ], request), request)
    except RuntimeError:
        raise ApiError("trusted_records_unavailable", "Trusted records are not ready.", 503) from None


@router.get("/people-places", response_model=Page[PeoplePlaceResponse])
def list_people_places(
    request: Annotated[EntityQuery, Depends()],
    repository: Annotated[EnrichmentRepository, Depends(get_enrichment_repository)],
) -> Page[PeoplePlaceResponse]:
    try:
        rows = _scoped_rows(repository, request)
        merchant_ids = {
            item.transaction_id: item.merchant_id
            for item in repository.list_merchant_evidence()
            if item.status == "confirmed" and item.merchant_id is not None
        }
        counterparty_ids = repository.list_counterparty_assignments()
    except RuntimeError:
        raise ApiError("trusted_records_unavailable", "Trusted records are not ready.", 503) from None
    return _page(
        _ordered(_people_places(rows, merchant_ids, counterparty_ids), request),
        request,
    )


@router.patch("/merchants/{merchant_id}", response_model=MutationResponse)
def correct_merchant(
    merchant_id: UUID,
    correction: MerchantCorrectionRequest,
    repository: Annotated[EnrichmentRepository, Depends(get_enrichment_repository)],
    refresh: Annotated[LocalWorkspaceRefresh, Depends(get_local_workspace_refresh)],
) -> MutationResponse:
    if repository.get_merchant(merchant_id) is None:
        raise ApiError("merchant_not_found", "The merchant was not found.", 404)
    if correction.category_id is not None and repository.get_category(correction.category_id) is None:
        raise ApiError("category_not_found", "The category was not found.", 404)
    if correction.descriptor is not None:
        repository.confirm_alias(correction.descriptor, merchant_id)
    if correction.category_id is not None:
        repository.assign_merchant_category(merchant_id, correction.category_id)
    try:
        refresh.refresh()
    except LocalRefreshError:
        raise ApiError(
            "local_refresh_failed",
            "The correction was saved, but local activity could not be refreshed.",
            503,
        ) from None
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
