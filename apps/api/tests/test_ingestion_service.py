from __future__ import annotations

from pathlib import Path

import fitz
import pytest
from spend_memory.ingestion.base import ParsedRawTransaction
from spend_memory.ingestion.registry import ParserRegistry
from spend_memory.ingestion.service import IngestionService
from spend_memory.storage.repository import (
    ImportLimits,
    ImportRepository,
    ImportRepositoryError,
)


class _Parser:
    parser_id = "test-parser"
    version = "1.0"

    def __init__(self) -> None:
        self.detection_calls = 0
        self.parse_calls = 0

    def can_parse(self, document: bytes, filename: str) -> float:
        self.detection_calls += 1
        return 1.0

    def parse(self, document: bytes) -> list[ParsedRawTransaction]:
        self.parse_calls += 1
        return [
            ParsedRawTransaction(
                date_text="2026-01-01",
                description_text="Test purchase",
                amount_text="-1200",
                currency_text="AED",
                source_page=None,
                source_row=2,
                source_text="2026-01-01,Test purchase,-1200",
                extraction_method="delimited_text",
            )
        ]


def _service(
    tmp_path: Path, parser: _Parser, *, max_bytes: int = 1024
) -> IngestionService:
    repository = ImportRepository(
        database_path=tmp_path / "spend-memory.duckdb",
        data_directory=tmp_path / "data",
        limits=ImportLimits(max_document_bytes=max_bytes),
    )
    return IngestionService(
        repository=repository,
        parser_registry=ParserRegistry([parser]),
    )


def _encrypted_pdf() -> bytes:
    with fitz.open() as pdf:
        pdf.new_page().insert_text((50, 50), "encrypted statement")
        return pdf.tobytes(
            encryption=fitz.PDF_ENCRYPT_AES_256,
            owner_pw="owner-secret",
            user_pw="user-secret",
        )


@pytest.mark.parametrize(
    ("document", "filename", "mime_type", "max_bytes", "expected_code"),
    (
        (b"too large", "statement.csv", "text/csv", 2, "document_too_large"),
        (b"valid text", "../statement.csv", "text/csv", 1024, "unsafe_filename"),
        (
            b"valid text",
            "statement.csv",
            "application/octet-stream",
            1024,
            "unsupported_mime_type",
        ),
        (
            b"valid text",
            "statement.pdf",
            "application/pdf",
            1024,
            "mime_type_mismatch",
        ),
    ),
)
def test_ingress_rejects_unsafe_documents_before_parser_selection(
    tmp_path: Path,
    document: bytes,
    filename: str,
    mime_type: str,
    max_bytes: int,
    expected_code: str,
) -> None:
    parser = _Parser()
    service = _service(tmp_path, parser, max_bytes=max_bytes)

    with pytest.raises(ImportRepositoryError) as caught:
        service.import_document(
            document=document,
            filename=filename,
            declared_mime_type=mime_type,
        )

    assert caught.value.code == expected_code
    assert parser.detection_calls == 0
    assert parser.parse_calls == 0


def test_ingress_selects_parser_only_after_validation_and_persists_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser = _Parser()
    service = _service(tmp_path, parser)
    validation_calls = 0
    real_validate_document = service.repository.validate_document

    def count_validation(**kwargs) -> None:
        nonlocal validation_calls
        validation_calls += 1
        real_validate_document(**kwargs)

    monkeypatch.setattr(service.repository, "validate_document", count_validation)

    result = service.import_document(
        document=b"valid text",
        filename="statement.csv",
        declared_mime_type="text/csv",
    )

    assert result.transaction_count == 1
    assert validation_calls == 1
    assert parser.detection_calls == 1
    assert parser.parse_calls == 1


def test_ingress_classifies_a_real_encrypted_pdf_before_parser_selection(
    tmp_path: Path,
) -> None:
    parser = _Parser()
    service = _service(tmp_path, parser, max_bytes=20 * 1024 * 1024)

    with pytest.raises(ImportRepositoryError) as caught:
        service.import_document(
            document=_encrypted_pdf(),
            filename="statement.pdf",
            declared_mime_type="application/pdf",
        )

    assert caught.value.code == "encrypted"
    assert parser.detection_calls == 0


def test_ingress_enforces_pdf_geometry_before_parser_selection(
    tmp_path: Path,
) -> None:
    parser = _Parser()
    repository = ImportRepository(
        database_path=tmp_path / "spend-memory.duckdb",
        data_directory=tmp_path / "data",
        limits=ImportLimits(
            max_document_bytes=20 * 1024 * 1024,
            max_pdf_page_width_points=600,
            max_pdf_page_height_points=900,
        ),
    )
    service = IngestionService(
        repository=repository,
        parser_registry=ParserRegistry([parser]),
    )
    with fitz.open() as pdf:
        pdf.new_page(width=601, height=842)
        document = pdf.tobytes()

    with pytest.raises(ImportRepositoryError) as caught:
        service.import_document(
            document=document,
            filename="statement.pdf",
            declared_mime_type="application/pdf",
        )

    assert caught.value.code == "pdf_page_dimensions"
    assert parser.detection_calls == 0


def test_ingress_enforces_pdf_preflight_deadline_before_parser_selection(
    tmp_path: Path,
) -> None:
    parser = _Parser()
    repository = ImportRepository(
        database_path=tmp_path / "spend-memory.duckdb",
        data_directory=tmp_path / "data",
        limits=ImportLimits(
            max_document_bytes=20 * 1024 * 1024,
            pdf_preflight_timeout_seconds=0,
        ),
    )
    service = IngestionService(
        repository=repository,
        parser_registry=ParserRegistry([parser]),
    )
    with fitz.open() as pdf:
        pdf.new_page()
        document = pdf.tobytes()

    with pytest.raises(ImportRepositoryError) as caught:
        service.import_document(
            document=document,
            filename="statement.pdf",
            declared_mime_type="application/pdf",
        )

    assert caught.value.code == "pdf_preflight_timeout"
    assert parser.detection_calls == 0


def test_ingress_pdf_preflight_has_a_killable_wall_time_deadline(
    tmp_path: Path,
) -> None:
    parser = _Parser()
    repository = ImportRepository(
        database_path=tmp_path / "spend-memory.duckdb",
        data_directory=tmp_path / "data",
        limits=ImportLimits(
            max_document_bytes=20 * 1024 * 1024,
            pdf_preflight_timeout_seconds=0.01,
        ),
    )
    service = IngestionService(
        repository=repository,
        parser_registry=ParserRegistry([parser]),
    )
    with fitz.open() as pdf:
        pdf.new_page()
        document = pdf.tobytes()

    with pytest.raises(ImportRepositoryError) as caught:
        service.import_document(
            document=document,
            filename="statement.pdf",
            declared_mime_type="application/pdf",
        )

    assert caught.value.code == "pdf_preflight_timeout"
    assert parser.detection_calls == 0
