from collections.abc import Sequence

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from spend_memory.api.contracts import ErrorBody, ErrorDetail, ErrorResponse


class ApiError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int,
        details: Sequence[ErrorDetail] = (),
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = tuple(details)


def _response(status_code: int, body: ErrorBody) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(error=body).model_dump(mode="json"),
    )


async def api_error_handler(_: Request, error: ApiError) -> JSONResponse:
    return _response(
        error.status_code,
        ErrorBody(code=error.code, message=error.message, details=list(error.details)),
    )


async def validation_error_handler(
    _: Request, error: RequestValidationError
) -> JSONResponse:
    details = [
        ErrorDetail(
            field=".".join(str(part) for part in item["loc"]),
            code=item["type"],
        )
        for item in error.errors()
    ]
    return _response(
        422,
        ErrorBody(
            code="invalid_request",
            message="The request is not valid.",
            details=details,
        ),
    )


async def http_error_handler(_: Request, error: HTTPException) -> JSONResponse:
    if error.status_code == 404:
        return _response(
            404,
            ErrorBody(
                code="not_found",
                message="The requested resource was not found.",
            ),
        )
    return _response(
        error.status_code,
        ErrorBody(code="request_failed", message="The request could not be completed."),
    )


async def unexpected_error_handler(_: Request, __: Exception) -> JSONResponse:
    return _response(
        500,
        ErrorBody(code="internal_error", message="The request could not be completed."),
    )
