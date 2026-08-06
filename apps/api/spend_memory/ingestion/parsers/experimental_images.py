from spend_memory.ingestion.base import ParsedRawTransaction, ParserCapabilities
from spend_memory.ingestion.registry import ParserErrorCode, StatementParserError


class SyntheticReceiptImageFixtureParser:
    parser_id = "synthetic-receipt-image"
    version = "0.1"
    capabilities = ParserCapabilities(False, True, False, True, True, experimental=True)

    def can_parse(self, document: bytes, filename: str) -> float:
        return 1.0 if filename.lower().endswith(".png") and document.startswith(b"SYNTHETIC RECEIPT IMAGE\n") else 0.0

    def parse(self, document: bytes) -> list[ParsedRawTransaction]:
        return _parse_fixture(document, b"SYNTHETIC RECEIPT IMAGE\n", "Synthetic receipt")


class SyntheticTransactionScreenshotFixtureParser:
    parser_id = "synthetic-transaction-screenshot"
    version = "0.1"
    capabilities = ParserCapabilities(False, True, False, True, True, experimental=True)

    def can_parse(self, document: bytes, filename: str) -> float:
        return 1.0 if filename.lower().endswith(".png") and document.startswith(b"SYNTHETIC TRANSACTION SCREENSHOT\n") else 0.0

    def parse(self, document: bytes) -> list[ParsedRawTransaction]:
        return _parse_fixture(document, b"SYNTHETIC TRANSACTION SCREENSHOT\n", "Synthetic screenshot")


def _parse_fixture(document: bytes, marker: bytes, description: str) -> list[ParsedRawTransaction]:
    if document != marker:
        raise StatementParserError(ParserErrorCode.MALFORMED)
    return [
        ParsedRawTransaction(
            date_text="2026-01-01",
            description_text=description,
            amount_text="-1200",
            currency_text="AED",
            source_page=1,
            source_row=1,
            source_text=marker.decode("ascii").strip(),
            extraction_method="synthetic_image_fixture",
            raw_account_identity="AED-SYNTH-001",
            extraction_confidence=1.0,
        )
    ]
