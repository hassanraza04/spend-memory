from pathlib import Path

import duckdb
import pytest
from spend_memory.ingestion.conformance import ParserFixture, assert_parser_conforms
from spend_memory.ingestion.parsers.canonical_csv import CanonicalCsvParser
from spend_memory.ingestion.parsers.experimental_images import (
    SyntheticReceiptImageFixtureParser,
    SyntheticTransactionScreenshotFixtureParser,
)
from spend_memory.ingestion.parsers.synthetic_pdf_a import SyntheticAedTabularPdfParser
from spend_memory.ingestion.parsers.synthetic_pdf_b import SyntheticPkrCompactPdfParser
from spend_memory.ingestion.registry import (
    ParserErrorCode,
    ParserRegistry,
    StatementParserError,
)
from spend_memory.ingestion.service import IngestionService
from spend_memory.storage.repository import ImportRepository

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIRECTORY = REPOSITORY_ROOT / "sample_data/source"


@pytest.mark.parametrize(
    ("parser", "fixture"),
    (
        (CanonicalCsvParser(), ParserFixture.from_file(SOURCE_DIRECTORY / "aed_january_2026.csv")),
        (SyntheticAedTabularPdfParser(), ParserFixture.from_file(SOURCE_DIRECTORY / "aed_statement_tabular.pdf")),
        (SyntheticPkrCompactPdfParser(), ParserFixture.from_file(SOURCE_DIRECTORY / "pkr_statement_compact.pdf")),
        (SyntheticReceiptImageFixtureParser(), ParserFixture.synthetic_image("synthetic-receipt.png")),
        (SyntheticTransactionScreenshotFixtureParser(), ParserFixture.synthetic_image("synthetic-screenshot.png")),
    ),
)
def test_parser_conformance_checks_typed_source_faithful_rows_and_safe_errors(parser, fixture) -> None:
    rows = assert_parser_conforms(parser, fixture)

    assert rows
    assert all(row.source_page is not None or row.source_row is not None for row in rows)
    assert all(isinstance(row.amount_text, str) and not hasattr(row, "amount_minor") for row in rows)


def test_experimental_adapters_cannot_bypass_safe_ingress_or_canonical_storage(tmp_path: Path) -> None:
    experimental = SyntheticReceiptImageFixtureParser()
    with pytest.raises(StatementParserError) as caught:
        ParserRegistry([experimental])._select_for_isolated_worker(
            ParserFixture.synthetic_image("synthetic-receipt.png").document,
            "synthetic-receipt.png",
        )

    assert caught.value.code is ParserErrorCode.UNSUPPORTED

    repository = ImportRepository(
        database_path=tmp_path / "spend-memory.duckdb",
        data_directory=tmp_path / "data",
    )
    result = IngestionService(
        repository=repository,
        parser_registry=ParserRegistry([CanonicalCsvParser(), experimental]),
    ).import_document(
        document=(SOURCE_DIRECTORY / "aed_january_2026.csv").read_bytes(),
        filename="aed_january_2026.csv",
        declared_mime_type="text/csv",
    )

    with duckdb.connect(str(tmp_path / "spend-memory.duckdb"), read_only=True) as connection:
        stored = connection.execute(
            "SELECT amount_text, source_row FROM raw_transactions WHERE import_run_id = ?",
            [result.run_id],
        ).fetchone()

    assert stored == ("-10847", 2)
