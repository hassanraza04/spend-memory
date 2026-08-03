from dataclasses import dataclass
from os import environ
from pathlib import Path
from shutil import rmtree
from typing import Annotated

import duckdb
from fastapi import Depends, Request

from spend_memory.enrichment.repository import EnrichmentRepository
from spend_memory.ingestion.parsers.canonical_csv import CanonicalCsvParser
from spend_memory.ingestion.parsers.synthetic_pdf_a import SyntheticAedTabularPdfParser
from spend_memory.ingestion.parsers.synthetic_pdf_b import SyntheticPkrCompactPdfParser
from spend_memory.ingestion.registry import ParserRegistry
from spend_memory.ingestion.service import IngestionService
from spend_memory.storage.repository import ImportRepository


@dataclass(frozen=True, slots=True)
class LocalSettings:
    database_path: Path
    data_directory: Path


class LocalDataService:
    _DEMO_PARSER_IDS = (
        "canonical-csv",
        "synthetic-aed-tabular-pdf",
        "synthetic-pkr-compact-pdf",
    )

    def __init__(self, settings: LocalSettings) -> None:
        self.settings = settings

    def reset_demo(self) -> None:
        if self.settings.database_path.exists():
            with duckdb.connect(str(self.settings.database_path), read_only=True) as connection:
                non_demo_import = connection.execute(
                    "SELECT 1 FROM import_runs WHERE parser_id NOT IN (?, ?, ?) LIMIT 1",
                    self._DEMO_PARSER_IDS,
                ).fetchone()
            if non_demo_import is not None:
                raise ValueError("non_demo_imports_present")
        self.delete()

    def delete(self) -> None:
        data_directory = self.settings.data_directory.resolve()
        if data_directory in {Path("/"), Path.home()}:
            raise ValueError("unsafe_local_data_path")
        if data_directory.exists():
            rmtree(data_directory)
        self.settings.database_path.unlink(missing_ok=True)
        self.settings.database_path.with_name(
            f".{self.settings.database_path.name}.write.lock"
        ).unlink(missing_ok=True)


def load_local_settings() -> LocalSettings:
    return LocalSettings(
        Path(environ.get("DUCKDB_PATH", "spend-memory.duckdb")),
        Path(environ.get("SPEND_MEMORY_DATA_DIRECTORY", "data")),
    )


def get_local_settings(request: Request) -> LocalSettings:
    return request.app.state.settings


def get_ingestion_service(
    settings: Annotated[LocalSettings, Depends(get_local_settings)],
) -> IngestionService:
    """Create the only production ingress for untrusted document bytes."""
    repository = ImportRepository(
        database_path=settings.database_path,
        data_directory=settings.data_directory,
    )
    return IngestionService(
        repository=repository,
        parser_registry=ParserRegistry(
            [
                CanonicalCsvParser(),
                SyntheticAedTabularPdfParser(),
                SyntheticPkrCompactPdfParser(),
            ]
        ),
    )


def get_enrichment_repository(
    settings: Annotated[LocalSettings, Depends(get_local_settings)],
) -> EnrichmentRepository:
    return EnrichmentRepository(settings.database_path)


def get_local_data_service(
    settings: Annotated[LocalSettings, Depends(get_local_settings)],
) -> LocalDataService:
    return LocalDataService(settings)
