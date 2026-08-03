from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from spend_memory.api import legacy_router, router
from spend_memory.api.dependencies import LocalSettings, load_local_settings
from spend_memory.api.errors import (
    ApiError,
    api_error_handler,
    http_error_handler,
    unexpected_error_handler,
    validation_error_handler,
)
from starlette.exceptions import HTTPException

LOCAL_API_HOST = "127.0.0.1"
LOCAL_API_PORT = 8000


def create_app(database_path: Path, data_directory: Path) -> FastAPI:
    app = FastAPI(title="Spend Memory API")
    app.state.settings = LocalSettings(database_path, data_directory, data_directory.parent)
    app.include_router(legacy_router)
    app.include_router(router)
    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(HTTPException, http_error_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)
    return app


settings = load_local_settings()
app = create_app(settings.database_path, settings.data_directory)


def run_local_api() -> None:
    uvicorn.run(app, host=LOCAL_API_HOST, port=LOCAL_API_PORT)


if __name__ == "__main__":
    run_local_api()
