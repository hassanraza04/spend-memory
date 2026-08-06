from dataclasses import dataclass
from pathlib import Path

from spend_memory.ingestion.base import (
    ParsedRawTransaction,
    ParserCapabilities,
    StatementParser,
)
from spend_memory.ingestion.registry import StatementParserError


@dataclass(frozen=True)
class ParserFixture:
    document: bytes
    filename: str
    malformed_document: bytes = b"not a statement"

    @classmethod
    def from_file(cls, path: Path) -> "ParserFixture":
        return cls(path.read_bytes(), path.name)

    @classmethod
    def synthetic_image(cls, filename: str) -> "ParserFixture":
        marker = b"SYNTHETIC RECEIPT IMAGE\n" if "receipt" in filename else b"SYNTHETIC TRANSACTION SCREENSHOT\n"
        return cls(marker, filename)


def assert_parser_conforms(
    parser: StatementParser,
    fixture: ParserFixture,
) -> tuple[ParsedRawTransaction, ...]:
    assert isinstance(parser.capabilities, ParserCapabilities)
    rows = parser.parse(fixture.document)
    assert isinstance(rows, list) and rows
    assert all(isinstance(row, ParsedRawTransaction) for row in rows)
    assert all(row.source_page is not None or row.source_row is not None for row in rows)
    assert all(isinstance(row.amount_text, str) and not hasattr(row, "amount_minor") for row in rows)
    try:
        parser.parse(fixture.malformed_document)
    except StatementParserError:
        pass
    else:
        raise AssertionError("parser must reject malformed input with a safe parser error")
    return tuple(rows)
