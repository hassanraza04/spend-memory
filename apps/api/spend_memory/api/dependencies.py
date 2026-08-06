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
from spend_memory.local_refresh import LocalWorkspaceRefresh
from spend_memory.storage.repository import ImportRepository


@dataclass(frozen=True, slots=True)
class LocalSettings:
    database_path: Path
    data_directory: Path
    app_data_root: Path


class LocalDataService:
    def __init__(self, settings: LocalSettings, refresh: LocalWorkspaceRefresh | None = None) -> None:
        self.settings = settings
        self.refresh = refresh or LocalWorkspaceRefresh(settings.database_path)

    def reset_demo(self) -> None:
        if self.settings.database_path.exists():
            with duckdb.connect(str(self.settings.database_path), read_only=True) as connection:
                non_demo_import = connection.execute(
                    "SELECT 1 FROM source_documents WHERE coalesce(is_demo, false) = false LIMIT 1",
                ).fetchone()
            if non_demo_import is not None:
                raise ValueError("non_demo_imports_present")
        self.delete()
        service = get_ingestion_service(self.settings)
        result = service.import_document(
            document=_DEMO_DOCUMENT,
            filename="aed_january_2026.csv",
            declared_mime_type="text/csv",
        )
        service.repository.mark_document_as_demo(result.document_id)
        self.refresh.refresh()

    def delete(self) -> None:
        root = _safe_local_path(self.settings.app_data_root, self.settings.app_data_root)
        data_directory = _safe_local_path(self.settings.data_directory, root)
        database_path = _safe_local_path(self.settings.database_path, root)
        if data_directory == root:
            raise ValueError("unsafe_local_data_path")
        if data_directory.exists():
            rmtree(data_directory)
        database_path.unlink(missing_ok=True)
        database_path.with_name(
            f".{database_path.name}.write.lock"
        ).unlink(missing_ok=True)


def load_local_settings() -> LocalSettings:
    data_directory = Path(environ.get("SPEND_MEMORY_DATA_DIRECTORY", "data"))
    return LocalSettings(
        Path(environ.get("DUCKDB_PATH", "spend-memory.duckdb")),
        data_directory,
        Path(environ.get("SPEND_MEMORY_APP_DATA_ROOT", data_directory.parent)),
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


def get_local_workspace_refresh(
    settings: Annotated[LocalSettings, Depends(get_local_settings)],
) -> LocalWorkspaceRefresh:
    return LocalWorkspaceRefresh(settings.database_path)


def get_local_data_service(
    settings: Annotated[LocalSettings, Depends(get_local_settings)],
) -> LocalDataService:
    return LocalDataService(settings, get_local_workspace_refresh(settings))


def _safe_local_path(path: Path, root: Path) -> Path:
    raw_path = path.absolute()
    raw_root = root.absolute()
    resolved_root = raw_root.resolve()
    resolved_path = raw_path.resolve()
    if (
        raw_root != resolved_root
        or raw_path != resolved_path
        or resolved_root in {Path("/"), Path.home()}
    ):
        raise ValueError("unsafe_local_data_path")
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError:
        raise ValueError("unsafe_local_data_path") from None
    return resolved_path


_DEMO_DOCUMENT = (
    b"transaction_id,posted_date,account_id,currency,amount_minor,description,transaction_type\n"
    b"SYN-00835,2026-01-01,AED-SYNTH-001,AED,-10847,BREW-LAB,debit\n"
    b"SYN-00834,2026-01-03,AED-SYNTH-001,AED,-13577,OrbitFuel Station,debit\n"
    b"SYN-00837,2026-01-03,AED-SYNTH-001,AED,-2999,STREAMBOX MONTHLY,debit\n"
    b"SYN-00830,2026-01-04,AED-SYNTH-001,AED,-13115,ORBIT FUEL,debit\n"
    b"SYN-00825,2026-01-06,AED-SYNTH-001,AED,-3988,PXLBKS,debit\n"
    b"SYN-00831,2026-01-06,AED-SYNTH-001,AED,-3936,QKCRT*ONLINE,debit\n"
    b"SYN-00838,2026-01-06,AED-SYNTH-001,AED,-12999,ATLAS COVER ANNUAL,debit\n"
    b"SYN-00836,2026-01-15,AED-SYNTH-001,AED,-13791,HBR PHARM,debit\n"
    b"SYN-00832,2026-01-17,AED-SYNTH-001,AED,-12297,OrbitFuel Station,debit\n"
    b"SYN-00826,2026-01-19,AED-SYNTH-001,AED,-5615,MetroMart POS,debit\n"
    b"SYN-00828,2026-01-20,AED-SYNTH-001,AED,-10569,ORBIT-FUEL,debit\n"
    b"SYN-00824,2026-01-22,AED-SYNTH-001,AED,-9340,Quick Cart,debit\n"
    b"SYN-00833,2026-01-24,AED-SYNTH-001,AED,-14015,HBR PHARM,debit\n"
    b"SYN-00829,2026-01-25,AED-SYNTH-001,AED,-18406,Harbor Pharm,debit\n"
    b"SYN-00823,2026-01-26,AED-SYNTH-001,AED,-947,HARBOR PHARMACY,debit\n"
    b"SYN-00827,2026-01-26,AED-SYNTH-001,AED,-3056,PixelBooks Online,debit\n"
    b"SYN-00821,2026-01-27,AED-SYNTH-001,AED,-3927,HBR PHARM,debit\n"
    b"SYN-00822,2026-01-27,AED-SYNTH-001,AED,-18054,ORBIT FUEL,debit\n"
)
