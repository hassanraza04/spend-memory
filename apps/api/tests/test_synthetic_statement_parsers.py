from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

import fitz
import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas
from spend_memory.ingestion.parsers.canonical_csv import CanonicalCsvParser
from spend_memory.ingestion.parsers.synthetic_pdf_a import SyntheticAedTabularPdfParser
from spend_memory.ingestion.parsers.synthetic_pdf_b import SyntheticPkrCompactPdfParser
from spend_memory.ingestion.registry import (
    ParserErrorCode,
    ParserRegistry,
    StatementParserError,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIRECTORY = REPOSITORY_ROOT / "sample_data/source"


def _expected_transactions() -> list[dict[str, object]]:
    ledger = json.loads(
        (REPOSITORY_ROOT / "sample_data/expected/canonical_ledger.json").read_text(
            encoding="utf-8"
        )
    )
    return ledger["transactions"]


def _parser_known_fields(parsed: object) -> tuple[str, str, str, str | None, str | None]:
    return (
        parsed.date_text,
        parsed.description_text,
        parsed.amount_text,
        parsed.currency_text,
        parsed.raw_account_identity,
    )


def _expected_known_fields(transaction: dict[str, object]) -> tuple[str, str, str, str, str]:
    amount_text = str(transaction["amount_minor"])
    if transaction["source_document"] == "source/pkr_statement_compact.pdf":
        amount_text = f"PKR {amount_text}"
    return (
        str(transaction["posted_date"]),
        str(transaction["description"]),
        amount_text,
        str(transaction["currency"]),
        str(transaction["account_id"]),
    )


def _aed_pdf_row(*, posted_date: str, amount: str) -> bytes:
    output = BytesIO()
    canvas = Canvas(output, pagesize=A4)
    canvas.drawString(50, 780, "SYNTHETIC AED STATEMENT | TABULAR LAYOUT")
    canvas.drawString(50, 750, "Date")
    canvas.drawString(150, 750, "Description")
    canvas.drawString(400, 750, "Amount (fils)")
    canvas.drawString(50, 730, posted_date)
    canvas.drawString(150, 730, "Test merchant")
    canvas.drawString(400, 730, amount)
    canvas.save()
    return output.getvalue()


def test_collective_parser_output_matches_the_expected_ledger() -> None:
    parsers_and_documents = (
        (CanonicalCsvParser(), "aed_january_2026.csv"),
        (SyntheticAedTabularPdfParser(), "aed_statement_tabular.pdf"),
        (SyntheticPkrCompactPdfParser(), "pkr_statement_compact.pdf"),
    )

    parsed = [
        transaction
        for parser, filename in parsers_and_documents
        for transaction in parser.parse((SOURCE_DIRECTORY / filename).read_bytes())
    ]

    expected = _expected_transactions()
    assert sorted(map(_parser_known_fields, parsed)) == sorted(
        _expected_known_fields(transaction) for transaction in expected
    )
    assert len(parsed) == len(expected)


def test_parser_versions_mark_the_explicit_provenance_contract() -> None:
    assert CanonicalCsvParser.version == "1.1"
    assert SyntheticAedTabularPdfParser.version == "1.2"
    assert SyntheticPkrCompactPdfParser.version == "1.1"


def test_each_parser_preserves_format_metadata_and_lineage() -> None:
    csv_transaction = CanonicalCsvParser().parse(
        (SOURCE_DIRECTORY / "aed_january_2026.csv").read_bytes()
    )[0]
    aed_transaction = SyntheticAedTabularPdfParser().parse(
        (SOURCE_DIRECTORY / "aed_statement_tabular.pdf").read_bytes()
    )[0]
    pkr_transaction = SyntheticPkrCompactPdfParser().parse(
        (SOURCE_DIRECTORY / "pkr_statement_compact.pdf").read_bytes()
    )[0]

    assert csv_transaction.source_page is None
    assert csv_transaction.source_row == 2
    assert csv_transaction.source_text == (
        "SYN-00835,2026-01-01,AED-SYNTH-001,AED,-10847,BREW-LAB,debit"
    )
    assert csv_transaction.extraction_confidence == 1.0
    assert csv_transaction.extraction_method == "delimited_text"

    assert pkr_transaction.amount_text == "PKR -182338"
    assert pkr_transaction.currency_text == "PKR"
    assert pkr_transaction.extraction_method == "embedded_text"
    assert aed_transaction.extraction_method == "embedded_text"

    for transaction, currency, account in (
        (aed_transaction, "AED", "AED-SYNTH-001"),
        (pkr_transaction, "PKR", "PKR-SYNTH-001"),
    ):
        assert transaction.currency_text == currency
        assert transaction.raw_account_identity == account
        assert transaction.source_page == 1
        assert transaction.source_row == 1
        assert transaction.source_text is not None
        assert transaction.date_text in transaction.source_text
        assert transaction.description_text in transaction.source_text
        assert transaction.amount_text in transaction.source_text
        assert transaction.extraction_confidence == 1.0


@pytest.mark.parametrize(
    ("filename", "parser_id"),
    (
        ("aed_january_2026.csv", "canonical-csv"),
        ("aed_statement_tabular.pdf", "synthetic-aed-tabular-pdf"),
        ("pkr_statement_compact.pdf", "synthetic-pkr-compact-pdf"),
    ),
)
def test_registry_selects_the_matching_synthetic_parser(filename: str, parser_id: str) -> None:
    registry = ParserRegistry(
        [CanonicalCsvParser(), SyntheticAedTabularPdfParser(), SyntheticPkrCompactPdfParser()]
    )

    selected = registry.select((SOURCE_DIRECTORY / filename).read_bytes(), filename)

    assert selected.parser_id == parser_id


@pytest.mark.parametrize(
    "document",
    (
        b"transaction_id;posted_date;account_id;currency;amount_minor;description;transaction_type\n",
        b"\xff\xfeinvalid",
        b"posted_date,account_id,currency,amount_minor,description,transaction_type\n",
    ),
)
def test_canonical_csv_rejects_wrong_delimiter_encoding_or_header(document: bytes) -> None:
    with pytest.raises(StatementParserError) as caught:
        CanonicalCsvParser().parse(document)

    assert caught.value.code is ParserErrorCode.MALFORMED


@pytest.mark.parametrize(
    ("posted_date", "amount"),
    (
        ("01/02/2025", "-1200"),
        ("2025-02-01", "-12.00"),
    ),
)
def test_aed_pdf_rejects_ambiguous_dates_and_amounts(posted_date: str, amount: str) -> None:
    with pytest.raises(StatementParserError) as caught:
        SyntheticAedTabularPdfParser().parse(
            _aed_pdf_row(posted_date=posted_date, amount=amount)
        )

    assert caught.value.code is ParserErrorCode.MALFORMED


@pytest.mark.parametrize(
    "parser",
    (SyntheticAedTabularPdfParser(), SyntheticPkrCompactPdfParser()),
)
def test_pdf_parsers_classify_real_encrypted_documents_as_encrypted(parser) -> None:
    with fitz.open() as pdf:
        pdf.new_page().insert_text((50, 50), "encrypted statement")
        encrypted = pdf.tobytes(
            encryption=fitz.PDF_ENCRYPT_AES_256,
            owner_pw="owner-secret",
            user_pw="user-secret",
        )

    with pytest.raises(StatementParserError) as caught:
        parser.parse(encrypted)

    assert caught.value.code is ParserErrorCode.ENCRYPTED
