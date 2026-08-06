from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile

from spend_memory.api.contracts import ImportResponse
from spend_memory.api.dependencies import get_ingestion_service
from spend_memory.api.errors import ApiError
from spend_memory.ingestion.service import IngestionService
from spend_memory.storage.repository import ImportRepositoryError

router = APIRouter()

_IMPORT_ERRORS = {
    "document_too_large": (413, "The document is too large."),
    "unsafe_filename": (422, "The filename is not valid."),
    "unsupported_mime_type": (422, "This file type is not supported."),
    "mime_type_mismatch": (422, "The file type does not match its contents."),
    "unsupported_document": (422, "This document is not supported."),
}


@router.post("/imports", response_model=ImportResponse, status_code=201)
async def import_document(
    file: Annotated[UploadFile, File()],
    service: Annotated[IngestionService, Depends(get_ingestion_service)],
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
    return ImportResponse(
        document_id=result.document_id,
        run_id=result.run_id,
        transaction_count=result.transaction_count,
        was_already_imported=result.was_already_imported,
        parser_id=result.parser_id,
        parser_version=result.parser_version,
    )
