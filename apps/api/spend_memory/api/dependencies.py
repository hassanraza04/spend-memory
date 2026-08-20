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
from spend_memory.storage.repository import ImportRepository, database_write_lock


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
        _seed_demo_enrichment(EnrichmentRepository(self.settings.database_path))
        self.refresh.refresh()

    def delete(self) -> None:
        root = _safe_local_path(self.settings.app_data_root, self.settings.app_data_root)
        data_directory = _safe_local_path(self.settings.data_directory, root)
        database_path = _safe_local_path(self.settings.database_path, root)
        with database_write_lock(database_path):
            if data_directory == root:
                raise ValueError("unsafe_local_data_path")
            if data_directory.exists():
                rmtree(data_directory)
            database_path.unlink(missing_ok=True)


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


def _seed_demo_enrichment(repository: EnrichmentRepository) -> None:
    for merchant_name, descriptors, category_label in _DEMO_MERCHANTS:
        merchant = repository.create_merchant(merchant_name)
        for descriptor in descriptors:
            repository.confirm_alias(descriptor, merchant.merchant_id)
        repository.record_confirmed_merchant_currency(merchant.merchant_id, "AED")
        category = repository.create_category(category_label)
        repository.assign_merchant_category(merchant.merchant_id, category.category_id)


_DEMO_MERCHANTS = (
    ("Brew Lab", ("BREW-LAB",), "Dining"),
    ("MetroMart", ("METROMART POS", "METRO MART MARKET"), "Groceries"),
    ("Orbit Fuel", ("ORBIT FUEL",), "Transport"),
    ("PixelBooks", ("PXLBKS",), "Books"),
    ("Quick Cart", ("QKCRT",), "Shopping"),
    ("Streambox", ("STREAMBOX MONTHLY",), "Entertainment"),
)


_DEMO_DOCUMENT = (
    b"transaction_id,posted_date,account_id,currency,amount_minor,description,transaction_type\n"
    b"SYN-00001,2026-01-01,AED-SYNTH-001,AED,5000,INCOMING TRANSFER,credit\n"
    b"SYN-00002,2026-01-03,AED-SYNTH-001,AED,-2999,STREAMBOX MONTHLY,debit\n"
    b"SYN-00003,2026-01-06,AED-SYNTH-001,AED,-850,BREW-LAB,debit\n"
    b"SYN-00004,2026-01-09,AED-SYNTH-001,AED,-7200,METROMART POS,debit\n"
    b"SYN-00005,2026-01-15,AED-SYNTH-001,AED,-13791,HBR PHARM,debit\n"
    b"SYN-00006,2026-01-23,AED-SYNTH-001,AED,-23577,ORBIT FUEL,debit\n"
    b"SYN-00007,2026-01-31,AED-SYNTH-001,AED,-3936,QKCRT*ONLINE,debit\n"
    b"SYN-00008,2026-02-01,AED-SYNTH-001,AED,7500,BANK TRANSFER CREDIT,credit\n"
    b"SYN-00009,2026-02-03,AED-SYNTH-001,AED,-3050,STREAMBOX MONTHLY,debit\n"
    b"SYN-00010,2026-02-06,AED-SYNTH-001,AED,-3988,PXLBKS,debit\n"
    b"SYN-00011,2026-02-12,AED-SYNTH-001,AED,-6500,METROMART POS,debit\n"
    b"SYN-00012,2026-02-18,AED-SYNTH-001,AED,-16000,ORBIT FUEL,debit\n"
    b"SYN-00013,2026-02-24,AED-SYNTH-001,AED,-4700,NOVA BAZAAR,debit\n"
    b"SYN-00014,2026-02-28,AED-SYNTH-001,AED,-9340,QKCRT*ONLINE,debit\n"
    b"SYN-00015,2026-03-01,AED-SYNTH-001,AED,10000,INCOMING TRANSFER,credit\n"
    b"SYN-00016,2026-03-03,AED-SYNTH-001,AED,-2999,STREAMBOX MONTHLY,debit\n"
    b"SYN-00017,2026-03-07,AED-SYNTH-001,AED,-1250,BREW-LAB,debit\n"
    b"SYN-00018,2026-03-12,AED-SYNTH-001,AED,-13900,METROMART POS,debit\n"
    b"SYN-00019,2026-03-19,AED-SYNTH-001,AED,-12297,ORBIT FUEL,debit\n"
    b"SYN-00020,2026-03-26,AED-SYNTH-001,AED,-3056,PXLBKS,debit\n"
    b"SYN-00021,2026-03-30,AED-SYNTH-001,AED,-2400,HBR PHARM,debit\n"
    b"SYN-00022,2026-04-01,AED-SYNTH-001,AED,12500,TRANSFER RECEIVED,credit\n"
    b"SYN-00023,2026-04-03,AED-SYNTH-001,AED,-3025,STREAMBOX MONTHLY,debit\n"
    b"SYN-00024,2026-04-07,AED-SYNTH-001,AED,-1900,BREW-LAB,debit\n"
    b"SYN-00025,2026-04-12,AED-SYNTH-001,AED,-12500,METROMART POS,debit\n"
    b"SYN-00026,2026-04-12,AED-SYNTH-001,AED,-12500,METRO MART MARKET,debit\n"
    b"SYN-00027,2026-04-20,AED-SYNTH-001,AED,-26920,QKCRT*ONLINE,debit\n"
    b"SYN-00028,2026-04-30,AED-SYNTH-001,AED,-17800,NOVA BAZAAR,debit\n"
)
