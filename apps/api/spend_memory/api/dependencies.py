from dataclasses import dataclass
from os import environ
from pathlib import Path
from typing import Annotated

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
