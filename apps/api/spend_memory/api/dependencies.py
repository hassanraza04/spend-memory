from dataclasses import dataclass
from os import environ
from pathlib import Path

from fastapi import Request


@dataclass(frozen=True, slots=True)
class LocalSettings:
    database_path: Path
    data_directory: Path


def load_local_settings() -> LocalSettings:
    return LocalSettings(
        Path(environ.get("DUCKDB_PATH", "spend-memory.duckdb")),
        Path(environ.get("SPEND_MEMORY_DATA_DIRECTORY", "data")),
    )


def get_local_settings(request: Request) -> LocalSettings:
    return request.app.state.settings
