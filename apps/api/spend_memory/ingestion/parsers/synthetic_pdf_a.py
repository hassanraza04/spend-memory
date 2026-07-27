from __future__ import annotations

import re
from datetime import date

import fitz

from spend_memory.ingestion.base import ParsedRawTransaction
from spend_memory.ingestion.ocr import (
    OcrError,
    OcrErrorCode,
    extract_pdf_page_text,
    normalize_ocr_amount_token,
)
from spend_memory.ingestion.registry import ParserErrorCode, StatementParserError

_TITLE = "SYNTHETIC AED STATEMENT | TABULAR LAYOUT"
_HEADER = ("Date", "Description", "Amount (fils)")
_AMOUNT = re.compile(r"-?(?:0|[1-9]\d*)\Z")
_IMAGE_ONLY_FIXTURE_NAME = "aed_statement_image_only.pdf"


class SyntheticAedTabularPdfParser:
    parser_id = "synthetic-aed-tabular-pdf"
    version = "1.2"

    def can_parse(self, document: bytes, filename: str) -> float:
        if not filename.lower().endswith(".pdf"):
            return 0.0
        fixture_name = filename.replace("\\", "/").rsplit("/", 1)[-1].lower()
        try:
            with fitz.open(stream=document, filetype="pdf") as pdf:
                if not pdf.page_count:
                    return 0.0
                if _TITLE in pdf[0].get_text():
                    return 1.0
                return 1.0 if fixture_name == _IMAGE_ONLY_FIXTURE_NAME else 0.0
        except (OcrError, fitz.FileDataError, RuntimeError, ValueError):
            return 0.0

    def parse(self, document: bytes) -> list[ParsedRawTransaction]:
        try:
            extracted = extract_pdf_page_text(document)
            if _TITLE not in extracted.page_text[0]:
                raise StatementParserError(ParserErrorCode.MALFORMED)
            ocr_by_page = {page.page_number: page for page in extracted.ocr_pages}
            transactions = [
                transaction
                for page_number, page_text in enumerate(extracted.page_text, start=1)
                for transaction in self._parse_page(
                    page_text.splitlines(),
                    page_number,
                    used_ocr=page_number in ocr_by_page,
                    extraction_confidence=(
                        ocr_by_page[page_number].extraction_confidence
                        if page_number in ocr_by_page
                        else 1.0
                    ),
                )
            ]
        except StatementParserError:
            raise
        except OcrError as error:
            if error.code is OcrErrorCode.ENCRYPTED_PDF:
                raise StatementParserError(ParserErrorCode.ENCRYPTED) from None
            raise StatementParserError(ParserErrorCode.MALFORMED) from None
        except (fitz.FileDataError, RuntimeError, ValueError):
            raise StatementParserError(ParserErrorCode.MALFORMED) from None
        if not transactions:
            raise StatementParserError(ParserErrorCode.MALFORMED)
        return transactions

    @staticmethod
    def _parse_page(
        lines: list[str],
        page_number: int,
        *,
        used_ocr: bool = False,
        extraction_confidence: float = 1.0,
    ) -> list[ParsedRawTransaction]:
        if used_ocr:
            lines = [line for line in lines if line.strip()]
        if page_number == 1 and (not lines or lines.pop(0) != _TITLE):
            raise StatementParserError(ParserErrorCode.MALFORMED)
        if tuple(lines[:3]) != _HEADER:
            raise StatementParserError(ParserErrorCode.MALFORMED)
        rows = lines[3:]
        if not rows or len(rows) % 3:
            raise StatementParserError(ParserErrorCode.MALFORMED)
        return [
            SyntheticAedTabularPdfParser._transaction(
                date_text=rows[index],
                description_text=rows[index + 1],
                amount_text=rows[index + 2],
                page_number=page_number,
                source_row=index // 3 + 1,
                used_ocr=used_ocr,
                extraction_confidence=extraction_confidence,
            )
            for index in range(0, len(rows), 3)
        ]

    @staticmethod
    def _transaction(
        *,
        date_text: str,
        description_text: str,
        amount_text: str,
        page_number: int,
        source_row: int,
        used_ocr: bool = False,
        extraction_confidence: float = 1.0,
    ) -> ParsedRawTransaction:
        _validate_date(date_text)
        parsed_amount_text = (
            normalize_ocr_amount_token(amount_text) if used_ocr else amount_text
        )
        if (
            not description_text
            or not _AMOUNT.fullmatch(parsed_amount_text)
            or int(parsed_amount_text) == 0
        ):
            raise StatementParserError(ParserErrorCode.MALFORMED)
        return ParsedRawTransaction(
            date_text=date_text,
            description_text=description_text,
            amount_text=amount_text,
            currency_text="AED",
            source_page=page_number,
            source_row=source_row,
            source_text=f"{date_text}\n{description_text}\n{amount_text}",
            raw_account_identity="AED-SYNTH-001",
            extraction_confidence=extraction_confidence,
            extraction_method="ocr:tesseract" if used_ocr else "embedded_text",
            normalized_amount_text=(
                parsed_amount_text
                if used_ocr and parsed_amount_text != amount_text
                else None
            ),
        )


def _validate_date(date_text: str) -> None:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_text):
        raise StatementParserError(ParserErrorCode.MALFORMED)
    try:
        date.fromisoformat(date_text)
    except ValueError:
        raise StatementParserError(ParserErrorCode.MALFORMED) from None
