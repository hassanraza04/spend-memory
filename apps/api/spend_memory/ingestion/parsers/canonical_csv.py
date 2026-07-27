from __future__ import annotations

import csv
import re
from datetime import date

from spend_memory.ingestion.base import ParsedRawTransaction
from spend_memory.ingestion.registry import ParserErrorCode, StatementParserError

_COLUMNS = (
    "transaction_id",
    "posted_date",
    "account_id",
    "currency",
    "amount_minor",
    "description",
    "transaction_type",
)
_TRANSACTION_ID = re.compile(r"SYN-\d{5}\Z")
_AMOUNT = re.compile(r"-?(?:0|[1-9]\d*)\Z")


class CanonicalCsvParser:
    parser_id = "canonical-csv"
    version = "1.0"

    def can_parse(self, document: bytes, filename: str) -> float:
        return 0.9 if filename.lower().endswith(".csv") else 0.0

    def parse(self, document: bytes) -> list[ParsedRawTransaction]:
        try:
            text = document.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise StatementParserError(ParserErrorCode.MALFORMED) from None
        if not text or "\r" in text:
            raise StatementParserError(ParserErrorCode.MALFORMED)

        lines = text.splitlines()
        if not lines:
            raise StatementParserError(ParserErrorCode.MALFORMED)
        try:
            header = next(csv.reader([lines[0]], delimiter=",", strict=True))
        except csv.Error:
            raise StatementParserError(ParserErrorCode.MALFORMED) from None
        if tuple(header) != _COLUMNS:
            raise StatementParserError(ParserErrorCode.MALFORMED)

        transactions: list[ParsedRawTransaction] = []
        for source_row, source_text in enumerate(lines[1:], start=2):
            try:
                row = next(csv.reader([source_text], delimiter=",", strict=True))
            except csv.Error:
                raise StatementParserError(ParserErrorCode.MALFORMED) from None
            if len(row) != len(_COLUMNS):
                raise StatementParserError(ParserErrorCode.MALFORMED)
            transactions.append(self._transaction(row, source_row, source_text))
        if not transactions:
            raise StatementParserError(ParserErrorCode.MALFORMED)
        return transactions

    @staticmethod
    def _transaction(
        row: list[str], source_row: int, source_text: str
    ) -> ParsedRawTransaction:
        transaction_id, date_text, account_id, currency, amount_text, description, transaction_type = row
        if not _TRANSACTION_ID.fullmatch(transaction_id):
            raise StatementParserError(ParserErrorCode.MALFORMED)
        _validate_date(date_text)
        _validate_amount(amount_text)
        if not account_id or currency not in {"AED", "PKR"} or not description:
            raise StatementParserError(ParserErrorCode.MALFORMED)
        amount = int(amount_text)
        if transaction_type not in {"debit", "credit"} or (
            transaction_type == "debit" and amount >= 0
        ) or (transaction_type == "credit" and amount <= 0):
            raise StatementParserError(ParserErrorCode.MALFORMED)
        return ParsedRawTransaction(
            date_text=date_text,
            description_text=description,
            amount_text=amount_text,
            currency_text=currency,
            source_page=None,
            source_row=source_row,
            source_text=source_text,
            raw_account_identity=account_id,
        )


def _validate_date(date_text: str) -> None:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_text):
        raise StatementParserError(ParserErrorCode.MALFORMED)
    try:
        date.fromisoformat(date_text)
    except ValueError:
        raise StatementParserError(ParserErrorCode.MALFORMED) from None


def _validate_amount(amount_text: str) -> None:
    if not _AMOUNT.fullmatch(amount_text) or int(amount_text) == 0:
        raise StatementParserError(ParserErrorCode.MALFORMED)
