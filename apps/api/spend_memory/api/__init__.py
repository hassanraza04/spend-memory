"""Versioned local API routes."""

from fastapi import APIRouter

from spend_memory.api.contracts import ErrorResponse, HealthResponse

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
