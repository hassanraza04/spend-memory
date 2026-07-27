from __future__ import annotations

from collections.abc import Iterable
from enum import Enum

from spend_memory.ingestion.base import ParsedRawTransaction, StatementParser


class ParserErrorCode(str, Enum):
    UNSUPPORTED = "unsupported"
    ENCRYPTED = "encrypted"
    MALFORMED = "malformed"
    AMBIGUOUS = "ambiguous"


class StatementParserError(Exception):
    def __init__(self, code: ParserErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


class ParserRegistry:
    def __init__(self, parsers: Iterable[StatementParser] = ()) -> None:
        self._parsers = list(parsers)

    def register(self, parser: StatementParser) -> None:
        self._parsers.append(parser)

    def select(self, document: bytes, filename: str) -> StatementParser:
        try:
            candidates = [
                (parser.can_parse(document, filename), parser) for parser in self._parsers
            ]
        except StatementParserError:
            raise
        except Exception:  # noqa: BLE001
            raise StatementParserError(ParserErrorCode.MALFORMED) from None
        compatible = [(confidence, parser) for confidence, parser in candidates if confidence > 0]
        if not compatible:
            raise StatementParserError(ParserErrorCode.UNSUPPORTED)
        highest_confidence = max(confidence for confidence, _ in compatible)
        selected = [
            parser for confidence, parser in compatible if confidence == highest_confidence
        ]
        if len(selected) != 1:
            raise StatementParserError(ParserErrorCode.AMBIGUOUS)
        return selected[0]

    def parse(self, document: bytes, filename: str) -> list[ParsedRawTransaction]:
        try:
            return self.select(document, filename).parse(document)
        except StatementParserError:
            raise
        except Exception:  # noqa: BLE001
            raise StatementParserError(ParserErrorCode.MALFORMED) from None
