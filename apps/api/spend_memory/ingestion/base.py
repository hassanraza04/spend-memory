from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


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


class StatementParser(Protocol):
    parser_id: str
    version: str

    def can_parse(self, document: bytes, filename: str) -> float: ...

    def parse(self, document: bytes) -> list[ParsedRawTransaction]: ...
