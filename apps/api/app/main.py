from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from spend_memory.api import router
from spend_memory.api.dependencies import LocalSettings
from spend_memory.api.errors import (
    ApiError,
    api_error_handler,
    http_error_handler,
    unexpected_error_handler,
    validation_error_handler,
)
from starlette.exceptions import HTTPException


def create_app(database_path: Path, data_directory: Path) -> FastAPI:
    app = FastAPI(title="Spend Memory API")
    app.state.settings = LocalSettings(database_path, data_directory)
    app.include_router(router)
    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(HTTPException, http_error_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)
    return app


app = create_app(Path("spend-memory.duckdb"), Path("data"))
