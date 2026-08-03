from typing import Annotated

from fastapi import APIRouter, Depends

from spend_memory.api.contracts import LocalDataConfirmation, LocalDataResponse
from spend_memory.api.dependencies import LocalDataService, get_local_data_service
from spend_memory.api.errors import ApiError

router = APIRouter()


@router.post("/demo/reset", response_model=LocalDataResponse)
def reset_demo(
    service: Annotated[LocalDataService, Depends(get_local_data_service)],
) -> LocalDataResponse:
    try:
        service.reset_demo()
    except ValueError:
        raise ApiError(
            "non_demo_imports_present",
            "Demo reset is unavailable while local imports are present.",
            409,
        ) from None
    return LocalDataResponse(status="reset")


@router.delete("/local-data", response_model=LocalDataResponse)
def delete_local_data(
    request: LocalDataConfirmation,
    service: Annotated[LocalDataService, Depends(get_local_data_service)],
) -> LocalDataResponse:
    try:
        service.delete()
    except ValueError:
        raise ApiError(
            "unsafe_local_data_path",
            "Local data could not be deleted safely.",
            409,
        ) from None
    return LocalDataResponse(status="deleted")
