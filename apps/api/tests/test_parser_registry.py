from __future__ import annotations

from dataclasses import FrozenInstanceError

import fitz
import pytest
from spend_memory.ingestion.base import ParsedRawTransaction
from spend_memory.ingestion.registry import (
    ParserErrorCode,
    ParserRegistry,
    StatementParserError,
)


class _Parser:
    def __init__(self, parser_id: str, confidence: float) -> None:
        self.parser_id = parser_id
        self.version = "1.0"
        self._confidence = confidence

    def can_parse(self, document: bytes, filename: str) -> float:
        return self._confidence

    def parse(self, document: bytes) -> list[ParsedRawTransaction]:
        return []


def test_registry_public_api_only_offers_isolated_document_selection() -> None:
    registry = ParserRegistry([_Parser("csv", 1.0)])

    assert not hasattr(registry, "select")
    assert not hasattr(registry, "parse")
    assert callable(registry.select_isolated)


def test_registry_selects_the_highest_confidence_compatible_parser() -> None:
    lower_confidence = _Parser("lower", 0.4)
    highest_confidence = _Parser("highest", 0.9)
    registry = ParserRegistry([lower_confidence, highest_confidence])

    selected = registry._select_for_isolated_worker(b"statement", "statement.csv")

    assert selected.parser_id == "highest"
    assert selected.version == "1.0"


def test_registry_refuses_tied_highest_confidence_parsers() -> None:
    registry = ParserRegistry([_Parser("first", 0.9), _Parser("second", 0.9)])

    with pytest.raises(StatementParserError) as caught:
        registry._select_for_isolated_worker(b"statement", "statement.csv")

    assert caught.value.code is ParserErrorCode.AMBIGUOUS


def test_registry_rejects_unsupported_files() -> None:
    registry = ParserRegistry([_Parser("csv", 0.0)])

    with pytest.raises(StatementParserError) as caught:
        registry._select_for_isolated_worker(b"unknown", "unknown.bin")

    assert caught.value.code is ParserErrorCode.UNSUPPORTED


def test_isolated_parser_rejects_bytes_other_than_the_selected_document() -> None:
    registry = ParserRegistry([_Parser("csv", 1.0)])
    parser = registry.select_isolated(
        b"first statement",
        "statement.csv",
        timeout_seconds=2.0,
    )

    try:
        with pytest.raises(StatementParserError) as caught:
            parser.parse(b"different statement")
    finally:
        parser.close()

    assert caught.value.code is ParserErrorCode.MALFORMED


def test_isolated_parser_exposes_no_detector_method() -> None:
    registry = ParserRegistry([_Parser("csv", 1.0)])
    parser = registry.select_isolated(
        b"statement",
        "statement.csv",
        timeout_seconds=2.0,
    )

    try:
        assert not hasattr(parser, "can_parse")
    finally:
        parser.close()


class _EncryptedParser(_Parser):
    def parse(self, document: bytes) -> list[ParsedRawTransaction]:
        raise StatementParserError(ParserErrorCode.ENCRYPTED)


def test_registry_preserves_declared_encrypted_document_errors() -> None:
    registry = ParserRegistry([_EncryptedParser("pdf", 1.0)])

    with pytest.raises(StatementParserError) as caught:
        registry._parse_for_tests(b"encrypted-pdf", "statement.pdf")

    assert caught.value.code is ParserErrorCode.ENCRYPTED


def test_registry_classifies_a_real_encrypted_pdf_as_encrypted() -> None:
    with fitz.open() as pdf:
        pdf.new_page().insert_text((50, 50), "encrypted statement")
        encrypted = pdf.tobytes(
            encryption=fitz.PDF_ENCRYPT_AES_256,
            owner_pw="owner-secret",
            user_pw="user-secret",
        )
    registry = ParserRegistry([_Parser("pdf", 1.0)])

    with pytest.raises(StatementParserError) as caught:
        registry._select_for_isolated_worker(encrypted, "statement.pdf")

    assert caught.value.code is ParserErrorCode.ENCRYPTED


class _BrokenParser(_Parser):
    def parse(self, document: bytes) -> list[ParsedRawTransaction]:
        raise ValueError("SENSITIVE-STATEMENT-DETAIL")


class _MemoryExhaustedParser(_Parser):
    def parse(self, document: bytes) -> list[ParsedRawTransaction]:
        raise MemoryError


def test_registry_maps_unexpected_parser_exceptions_to_safe_malformed_errors() -> None:
    registry = ParserRegistry([_BrokenParser("csv", 1.0)])

    with pytest.raises(StatementParserError) as caught:
        registry._parse_for_tests(b"not-a-statement", "statement.csv")

    assert caught.value.code is ParserErrorCode.MALFORMED
    assert str(caught.value) == "malformed"
    assert "SENSITIVE-STATEMENT-DETAIL" not in str(caught.value)
    assert caught.value.__cause__ is None


def test_registry_maps_memory_exhaustion_to_a_safe_resource_error() -> None:
    registry = ParserRegistry([_MemoryExhaustedParser("csv", 1.0)])

    with pytest.raises(StatementParserError) as caught:
        registry._parse_for_tests(b"not-a-statement", "statement.csv")

    assert caught.value.code is ParserErrorCode.RESOURCE_LIMIT
    assert str(caught.value) == "resource_limit"
    assert caught.value.__cause__ is None


class _BrokenDetector(_Parser):
    def can_parse(self, document: bytes, filename: str) -> float:
        raise RuntimeError("SENSITIVE-STATEMENT-DETAIL")


def test_registry_maps_unexpected_detector_exceptions_to_safe_malformed_errors() -> None:
    registry = ParserRegistry([_BrokenDetector("csv", 1.0)])

    with pytest.raises(StatementParserError) as caught:
        registry._select_for_isolated_worker(b"not-a-statement", "statement.csv")

    assert caught.value.code is ParserErrorCode.MALFORMED
    assert str(caught.value) == "malformed"
    assert "SENSITIVE-STATEMENT-DETAIL" not in str(caught.value)
    assert caught.value.__cause__ is None


def test_parser_output_is_immutable_and_retains_source_amount_text() -> None:
    parsed = ParsedRawTransaction(
        date_text="2026-01-02",
        description_text="Coffee shop",
        amount_text="- AED 12.50",
        currency_text="AED",
        source_page=1,
        source_row=7,
        source_text="02 Jan Coffee shop - AED 12.50",
        raw_account_identity="AED-SYNTH-001",
        raw_account_reference="001",
        raw_balance_text="AED 88.20",
        extraction_confidence=0.95,
        extraction_method="embedded_text",
    )

    assert parsed.amount_text == "- AED 12.50"
    with pytest.raises(FrozenInstanceError):
        parsed.amount_text = "AED 12.50"  # type: ignore[misc]


def test_parser_output_requires_explicit_extraction_method() -> None:
    with pytest.raises(TypeError):
        ParsedRawTransaction(  # type: ignore[call-arg]
            date_text="2026-01-02",
            description_text="Coffee shop",
            amount_text="-1250",
            currency_text="AED",
            source_page=1,
            source_row=7,
            source_text="2026-01-02 Coffee shop -1250",
        )
