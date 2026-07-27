from __future__ import annotations

from dataclasses import FrozenInstanceError

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


def test_registry_selects_the_highest_confidence_compatible_parser() -> None:
    lower_confidence = _Parser("lower", 0.4)
    highest_confidence = _Parser("highest", 0.9)
    registry = ParserRegistry([lower_confidence, highest_confidence])

    selected = registry.select(b"statement", "statement.csv")

    assert selected.parser_id == "highest"
    assert selected.version == "1.0"


def test_registry_refuses_tied_highest_confidence_parsers() -> None:
    registry = ParserRegistry([_Parser("first", 0.9), _Parser("second", 0.9)])

    with pytest.raises(StatementParserError) as caught:
        registry.select(b"statement", "statement.csv")

    assert caught.value.code is ParserErrorCode.AMBIGUOUS


def test_registry_rejects_unsupported_files() -> None:
    registry = ParserRegistry([_Parser("csv", 0.0)])

    with pytest.raises(StatementParserError) as caught:
        registry.select(b"unknown", "unknown.bin")

    assert caught.value.code is ParserErrorCode.UNSUPPORTED


class _EncryptedParser(_Parser):
    def parse(self, document: bytes) -> list[ParsedRawTransaction]:
        raise StatementParserError(ParserErrorCode.ENCRYPTED)


def test_registry_preserves_declared_encrypted_document_errors() -> None:
    registry = ParserRegistry([_EncryptedParser("pdf", 1.0)])

    with pytest.raises(StatementParserError) as caught:
        registry.parse(b"encrypted-pdf", "statement.pdf")

    assert caught.value.code is ParserErrorCode.ENCRYPTED


class _BrokenParser(_Parser):
    def parse(self, document: bytes) -> list[ParsedRawTransaction]:
        raise ValueError("SENSITIVE-STATEMENT-DETAIL")


def test_registry_maps_unexpected_parser_exceptions_to_safe_malformed_errors() -> None:
    registry = ParserRegistry([_BrokenParser("csv", 1.0)])

    with pytest.raises(StatementParserError) as caught:
        registry.parse(b"not-a-statement", "statement.csv")

    assert caught.value.code is ParserErrorCode.MALFORMED
    assert str(caught.value) == "malformed"
    assert "SENSITIVE-STATEMENT-DETAIL" not in str(caught.value)
    assert caught.value.__cause__ is None


class _BrokenDetector(_Parser):
    def can_parse(self, document: bytes, filename: str) -> float:
        raise RuntimeError("SENSITIVE-STATEMENT-DETAIL")


def test_registry_maps_unexpected_detector_exceptions_to_safe_malformed_errors() -> None:
    registry = ParserRegistry([_BrokenDetector("csv", 1.0)])

    with pytest.raises(StatementParserError) as caught:
        registry.select(b"not-a-statement", "statement.csv")

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
    )

    assert parsed.amount_text == "- AED 12.50"
    with pytest.raises(FrozenInstanceError):
        parsed.amount_text = "AED 12.50"  # type: ignore[misc]
