from __future__ import annotations

import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from time import monotonic

import fitz


class OcrErrorCode(str, Enum):
    PAGE_LIMIT = "ocr_page_limit"
    IMAGE_DIMENSIONS = "ocr_image_dimensions"
    IMAGE_PIXELS = "ocr_image_pixels"
    TIMEOUT = "ocr_timeout"
    ENGINE = "ocr_engine"
    MALFORMED_PDF = "ocr_malformed_pdf"


class OcrError(Exception):
    def __init__(self, code: OcrErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True)
class OcrLimits:
    max_pages: int = 20
    render_dpi: int = 200
    max_image_width: int = 2_500
    max_image_height: int = 3_500
    max_image_pixels: int = 8_000_000
    timeout_seconds: float = 15.0


DEFAULT_OCR_LIMITS = OcrLimits()


@dataclass(frozen=True)
class OcrPageText:
    page_number: int
    text: str
    engine: str = "tesseract"
    extraction_confidence: float = 0.65


@dataclass(frozen=True)
class PdfPageTextResult:
    page_text: tuple[str, ...]
    ocr_pages: tuple[OcrPageText, ...]


OcrRunner = Callable[[bytes, float], str]


def _has_usable_text(text: str) -> bool:
    return sum(character.isalnum() for character in text) >= 3


def extract_pdf_page_text(
    document: bytes,
    *,
    limits: OcrLimits = DEFAULT_OCR_LIMITS,
    runner: OcrRunner | None = None,
) -> PdfPageTextResult:
    try:
        with fitz.open(stream=document, filetype="pdf") as pdf:
            if pdf.needs_pass or not pdf.page_count:
                raise OcrError(OcrErrorCode.MALFORMED_PDF)
            page_text = [page.get_text() for page in pdf]
            textless_pages = [
                index for index, text in enumerate(page_text) if not _has_usable_text(text)
            ]
            if not textless_pages:
                return PdfPageTextResult(tuple(page_text), ())
            if pdf.page_count > limits.max_pages:
                raise OcrError(OcrErrorCode.PAGE_LIMIT)

            ocr_pages: list[OcrPageText] = []
            ocr_runner = runner or run_tesseract
            deadline = monotonic() + limits.timeout_seconds
            for page_index in textless_pages:
                pixmap = pdf[page_index].get_pixmap(
                    dpi=limits.render_dpi,
                    colorspace=fitz.csGRAY,
                    alpha=False,
                    annots=False,
                )
                if (
                    pixmap.width > limits.max_image_width
                    or pixmap.height > limits.max_image_height
                ):
                    raise OcrError(OcrErrorCode.IMAGE_DIMENSIONS)
                if pixmap.width * pixmap.height > limits.max_image_pixels:
                    raise OcrError(OcrErrorCode.IMAGE_PIXELS)
                remaining_seconds = deadline - monotonic()
                if remaining_seconds <= 0:
                    raise OcrError(OcrErrorCode.TIMEOUT)
                text = ocr_runner(pixmap.tobytes("png"), remaining_seconds)
                page_text[page_index] = text
                ocr_pages.append(OcrPageText(page_number=page_index + 1, text=text))
    except OcrError:
        raise
    except (fitz.FileDataError, RuntimeError, ValueError):
        raise OcrError(OcrErrorCode.MALFORMED_PDF) from None
    return PdfPageTextResult(tuple(page_text), tuple(ocr_pages))


def run_tesseract(
    image: bytes,
    timeout_seconds: float,
    *,
    executable: str = "tesseract",
) -> str:
    command = [
        executable,
        "stdin",
        "stdout",
        "--dpi",
        "200",
        "--psm",
        "6",
        "-l",
        "eng",
    ]
    try:
        completed = subprocess.run(
            command,
            input=image,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise OcrError(OcrErrorCode.TIMEOUT) from None
    except OSError:
        raise OcrError(OcrErrorCode.ENGINE) from None
    if completed.returncode:
        raise OcrError(OcrErrorCode.ENGINE)
    return completed.stdout.decode("utf-8", errors="replace")


def normalize_ocr_amount_token(source: str) -> str:
    if re.fullmatch(r"[+-]?[0-9OIl]+", source) is None:
        return source
    if not any(character.isdigit() or character in "Il" for character in source):
        return source
    normalized = source.translate(str.maketrans({"O": "0", "I": "1", "l": "1"}))
    if re.fullmatch(r"[+-]?(?:0|[1-9]\d*)", normalized) is None:
        return source
    if int(normalized) == 0:
        return source
    return normalized
