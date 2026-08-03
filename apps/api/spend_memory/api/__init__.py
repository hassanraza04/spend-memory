"""Versioned local API routes."""

from fastapi import APIRouter

from spend_memory.api.contracts import ErrorResponse, HealthResponse
from spend_memory.api.routes.counterparties import router as counterparties_router
from spend_memory.api.routes.imports import router as imports_router
from spend_memory.api.routes.search import router as search_router
from spend_memory.api.routes.transactions import router as transactions_router

router = APIRouter(
    prefix="/api/v1",
    responses={
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


router.include_router(imports_router)
router.include_router(transactions_router)
router.include_router(search_router)
router.include_router(counterparties_router)


legacy_router = APIRouter()
legacy_router.add_api_route(
    "/health",
    health,
    methods=["GET"],
    response_model=HealthResponse,
    include_in_schema=False,
)
