from dataclasses import dataclass
from pathlib import Path

from fastapi import Request


@dataclass(frozen=True, slots=True)
class LocalSettings:
    database_path: Path
    data_directory: Path


def get_local_settings(request: Request) -> LocalSettings:
    return request.app.state.settings
