from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ParserCapabilities:
    text_extraction: bool
    requires_ocr: bool
    supports_balance: bool
    discovers_currency: bool
    reports_confidence: bool
    experimental: bool = False


@dataclass(frozen=True)
class ParsedRawTransaction:
    """A source-faithful transaction extracted before persistence assigns IDs."""

    date_text: str
    description_text: str
    amount_text: str
    currency_text: str | None
    source_page: int | None
    source_row: int | None
    source_text: str | None
    extraction_method: str
    raw_account_identity: str | None = None
    raw_account_reference: str | None = None
    raw_balance_text: str | None = None
    extraction_confidence: float = 1.0
    normalized_amount_text: str | None = None


class StatementParser(Protocol):
    """Immutable parser contract used across a spawned local worker boundary.

    Implementations registered for service ingestion must be serializable by
    Python's standard ``pickle`` module and multiprocessing ``spawn`` context.
    """

    parser_id: str
    version: str
    capabilities: ParserCapabilities

    def can_parse(self, document: bytes, filename: str) -> float: ...

    def parse(self, document: bytes) -> list[ParsedRawTransaction]: ...
