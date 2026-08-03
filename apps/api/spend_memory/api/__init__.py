"""Versioned local API routes."""

from fastapi import APIRouter

from spend_memory.api.contracts import HealthResponse

router = APIRouter(prefix="/api/v1")


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")
