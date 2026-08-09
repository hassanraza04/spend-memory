from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile

from spend_memory.api.contracts import ImportInspectionResponse, ImportResponse
from spend_memory.api.dependencies import (
    get_ingestion_service,
    get_local_workspace_refresh,
)
from spend_memory.api.errors import ApiError
from spend_memory.ingestion.service import IngestionService
from spend_memory.local_refresh import LocalRefreshError, LocalWorkspaceRefresh
from spend_memory.storage.repository import ImportRepositoryError

router = APIRouter()

_IMPORT_ERRORS = {
    "document_too_large": (413, "The document is too large."),
    "unsafe_filename": (422, "The filename is not valid."),
    "unsupported_mime_type": (422, "This file type is not supported."),
    "mime_type_mismatch": (422, "The file type does not match its contents."),
    "unsupported_document": (422, "This document is not supported."),
    "import_not_found": (404, "The import was not found."),
    "storage_failed": (409, "The stored document is not available."),
}


def _response(result) -> ImportResponse:
    return ImportResponse(
        document_id=result.document_id,
        run_id=result.run_id,
        transaction_count=result.transaction_count,
        was_already_imported=result.was_already_imported,
        parser_id=result.parser_id,
        parser_version=result.parser_version,
    )


@router.post("/imports", response_model=ImportResponse, status_code=201)
async def import_document(
    file: Annotated[UploadFile, File()],
    service: Annotated[IngestionService, Depends(get_ingestion_service)],
    refresh: Annotated[LocalWorkspaceRefresh, Depends(get_local_workspace_refresh)],
) -> ImportResponse:
    try:
        result = service.import_document(
            document=await file.read(),
            filename=file.filename or "",
            declared_mime_type=file.content_type or "",
        )
    except ImportRepositoryError as error:
        status_code, message = _IMPORT_ERRORS.get(
            error.code, (422, "The document could not be imported.")
        )
        raise ApiError(error.code, message, status_code) from None
    try:
        refresh.refresh()
    except LocalRefreshError:
        raise ApiError(
            "local_refresh_failed",
            "The statement was saved, but local activity could not be refreshed.",
            503,
        ) from None
    return _response(result)


@router.get("/imports/{document_id}", response_model=ImportInspectionResponse)
def inspect_import(
    document_id: UUID,
    service: Annotated[IngestionService, Depends(get_ingestion_service)],
) -> ImportInspectionResponse:
    inspection = service.inspect_document(document_id)
    if inspection is None:
        raise ApiError("import_not_found", "The import was not found.", 404)
    return ImportInspectionResponse(**inspection.__dict__)


@router.post("/imports/{document_id}/reprocess", response_model=ImportResponse, status_code=201)
def reprocess_import(
    document_id: UUID,
    service: Annotated[IngestionService, Depends(get_ingestion_service)],
    refresh: Annotated[LocalWorkspaceRefresh, Depends(get_local_workspace_refresh)],
) -> ImportResponse:
    try:
        result = service.reprocess_document(document_id)
    except ImportRepositoryError as error:
        status_code, message = _IMPORT_ERRORS.get(
            error.code, (422, "The document could not be imported.")
        )
        raise ApiError(error.code, message, status_code) from None
    try:
        refresh.refresh()
    except LocalRefreshError:
        raise ApiError(
            "local_refresh_failed",
            "The statement was saved, but local activity could not be refreshed.",
            503,
        ) from None
    return _response(result)
