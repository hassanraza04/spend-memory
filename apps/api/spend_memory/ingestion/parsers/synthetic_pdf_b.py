from __future__ import annotations

import re
from datetime import date

import fitz

from spend_memory.ingestion.base import ParsedRawTransaction
from spend_memory.ingestion.registry import ParserErrorCode, StatementParserError

_TITLE = "SYNTHETIC PKR ACTIVITY"
_AMOUNT = re.compile(r"PKR (-?(?:0|[1-9]\d*))\Z")


class SyntheticPkrCompactPdfParser:
    parser_id = "synthetic-pkr-compact-pdf"
    version = "1.0"

    def can_parse(self, document: bytes, filename: str) -> float:
        if not filename.lower().endswith(".pdf"):
            return 0.0
        try:
            with fitz.open(stream=document, filetype="pdf") as pdf:
                return 1.0 if pdf.page_count and _TITLE in pdf[0].get_text() else 0.0
        except (fitz.FileDataError, RuntimeError, ValueError):
            return 0.0

    def parse(self, document: bytes) -> list[ParsedRawTransaction]:
        try:
            with fitz.open(stream=document, filetype="pdf") as pdf:
                if pdf.needs_pass or not pdf.page_count:
                    raise StatementParserError(ParserErrorCode.MALFORMED)
                transactions = [
                    transaction
                    for page_number, page in enumerate(pdf, start=1)
                    for transaction in self._parse_page(page.get_text().splitlines(), page_number)
                ]
        except StatementParserError:
            raise
        except (fitz.FileDataError, RuntimeError, ValueError):
            raise StatementParserError(ParserErrorCode.MALFORMED) from None
        if not transactions:
            raise StatementParserError(ParserErrorCode.MALFORMED)
        return transactions

    @staticmethod
    def _parse_page(lines: list[str], page_number: int) -> list[ParsedRawTransaction]:
        if not lines or lines.pop(0) != _TITLE:
            raise StatementParserError(ParserErrorCode.MALFORMED)
        if not lines or len(lines) % 3:
            raise StatementParserError(ParserErrorCode.MALFORMED)
        return [
            SyntheticPkrCompactPdfParser._transaction(
                description_text=lines[index],
                date_text=lines[index + 1],
                amount_line=lines[index + 2],
                page_number=page_number,
                source_row=index // 3 + 1,
            )
            for index in range(0, len(lines), 3)
        ]

    @staticmethod
    def _transaction(
        *,
        description_text: str,
        date_text: str,
        amount_line: str,
        page_number: int,
        source_row: int,
    ) -> ParsedRawTransaction:
        _validate_date(date_text)
        amount_match = _AMOUNT.fullmatch(amount_line)
        if not description_text or amount_match is None or int(amount_match.group(1)) == 0:
            raise StatementParserError(ParserErrorCode.MALFORMED)
        return ParsedRawTransaction(
            date_text=date_text,
            description_text=description_text,
            amount_text=amount_line,
            currency_text="PKR",
            source_page=page_number,
            source_row=source_row,
            source_text=f"{description_text}\n{date_text}\n{amount_line}",
            raw_account_identity="PKR-SYNTH-001",
        )


def _validate_date(date_text: str) -> None:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_text):
        raise StatementParserError(ParserErrorCode.MALFORMED)
    try:
        date.fromisoformat(date_text)
    except ValueError:
        raise StatementParserError(ParserErrorCode.MALFORMED) from None
