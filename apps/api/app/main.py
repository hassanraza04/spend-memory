from asyncio import Lock
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
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
LOCAL_WEB_ORIGINS = {"http://127.0.0.1:3000", "http://localhost:3000"}


def create_app(database_path: Path, data_directory: Path) -> FastAPI:
    app = FastAPI(title="Spend Memory API")
    app.state.settings = LocalSettings(database_path, data_directory, data_directory.parent)
    app.state.database_request_lock = Lock()

    @app.middleware("http")
    async def serialize_local_database_access(request, call_next):
        async with app.state.database_request_lock:
            return await call_next(request)

    @app.middleware("http")
    async def reject_cross_origin_mutations(request, call_next):
        if (
            request.method in {"POST", "PATCH", "DELETE"}
            and (origin := request.headers.get("origin")) is not None
            and origin not in LOCAL_WEB_ORIGINS
        ):
            return JSONResponse(
                status_code=403,
                content={
                    "error": {
                        "code": "cross_origin_request",
                        "message": "This local request is not allowed.",
                        "details": [],
                    }
                },
            )
        return await call_next(request)

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
