from __future__ import annotations

import subprocess
from hashlib import sha256
from io import BytesIO
from pathlib import Path

import fitz
import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas
from spend_memory.ingestion.ocr import (
    OcrError,
    OcrErrorCode,
    OcrLimits,
    extract_pdf_page_text,
    normalize_ocr_amount_token,
    run_tesseract,
)
from spend_memory.ingestion.parsers.synthetic_pdf_a import SyntheticAedTabularPdfParser
from spend_memory.ingestion.registry import ParserRegistry

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
IMAGE_ONLY_FIXTURE = REPOSITORY_ROOT / "sample_data/source/aed_statement_image_only.pdf"


def _text_pdf(*lines: str) -> bytes:
    output = BytesIO()
    canvas = Canvas(output, pagesize=A4)
    for index, line in enumerate(lines):
        canvas.drawString(50, 780 - index * 20, line)
    canvas.save()
    return output.getvalue()


def _blank_pdf(*, pages: int = 1, width: float = 595, height: float = 842) -> bytes:
    document = fitz.open()
    for _ in range(pages):
        document.new_page(width=width, height=height)
    result = document.tobytes()
    document.close()
    return result


def test_embedded_text_on_every_page_skips_tesseract() -> None:
    calls: list[bytes] = []

    result = extract_pdf_page_text(
        _text_pdf("page has usable text"),
        runner=lambda image, timeout: calls.append(image) or "unexpected OCR",
    )

    assert calls == []
    assert result.page_text == ("page has usable text\n",)
    assert result.ocr_pages == ()


def test_only_textless_pages_use_tesseract_and_ocr_text_is_separate() -> None:
    document = fitz.open()
    first = document.new_page()
    first.insert_text((50, 50), "embedded page text")
    document.new_page()
    original = document.tobytes()
    document.close()
    original_hash = sha256(original).hexdigest()

    result = extract_pdf_page_text(
        original,
        runner=lambda image, timeout: "OCR second page\n",
    )

    assert result.page_text == ("embedded page text\n", "OCR second page\n")
    assert tuple(page.page_number for page in result.ocr_pages) == (2,)
    assert result.ocr_pages[0].text == "OCR second page\n"
    assert result.ocr_pages[0].engine == "tesseract"
    assert sha256(original).hexdigest() == original_hash


def test_ocr_rejects_documents_over_the_page_limit_before_running_tesseract() -> None:
    called = False

    def runner(image: bytes, timeout: float) -> str:
        nonlocal called
        called = True
        return ""

    with pytest.raises(OcrError) as caught:
        extract_pdf_page_text(
            _blank_pdf(pages=2),
            limits=OcrLimits(max_pages=1),
            runner=runner,
        )

    assert caught.value.code is OcrErrorCode.PAGE_LIMIT
    assert str(caught.value) == "ocr_page_limit"
    assert called is False


@pytest.mark.parametrize(
    ("limits", "expected_code"),
    (
        (OcrLimits(render_dpi=144, max_image_width=100), OcrErrorCode.IMAGE_DIMENSIONS),
        (OcrLimits(render_dpi=144, max_image_height=100), OcrErrorCode.IMAGE_DIMENSIONS),
        (OcrLimits(render_dpi=144, max_image_pixels=10_000), OcrErrorCode.IMAGE_PIXELS),
    ),
)
def test_ocr_enforces_rendered_image_limits_before_tesseract(
    limits: OcrLimits,
    expected_code: OcrErrorCode,
) -> None:
    with pytest.raises(OcrError) as caught:
        extract_pdf_page_text(
            _blank_pdf(),
            limits=limits,
            runner=lambda image, timeout: pytest.fail("Tesseract must not run"),
        )

    assert caught.value.code is expected_code


def test_tesseract_timeout_is_mapped_to_a_safe_error(monkeypatch) -> None:
    def time_out(*args, **kwargs):
        raise subprocess.TimeoutExpired(
            cmd=["tesseract", "stdin", "stdout"],
            timeout=0.01,
            output=b"SENSITIVE OCR OUTPUT",
        )

    monkeypatch.setattr(subprocess, "run", time_out)

    with pytest.raises(OcrError) as caught:
        run_tesseract(b"png bytes", timeout_seconds=0.01)

    assert caught.value.code is OcrErrorCode.TIMEOUT
    assert str(caught.value) == "ocr_timeout"
    assert caught.value.__cause__ is None
    assert "SENSITIVE" not in str(caught.value)


def test_tesseract_failure_is_safe_and_invocation_uses_an_argument_list(monkeypatch) -> None:
    invocation: dict[str, object] = {}

    def fail(command, **kwargs):
        invocation["command"] = command
        invocation.update(kwargs)
        return subprocess.CompletedProcess(
            command,
            returncode=1,
            stdout=b"",
            stderr=b"SENSITIVE OCR ERROR",
        )

    monkeypatch.setattr(subprocess, "run", fail)

    with pytest.raises(OcrError) as caught:
        run_tesseract(b"png bytes", timeout_seconds=2.5)

    assert caught.value.code is OcrErrorCode.ENGINE
    assert str(caught.value) == "ocr_engine"
    assert invocation["command"] == [
        "tesseract",
        "stdin",
        "stdout",
        "--dpi",
        "200",
        "--psm",
        "6",
        "-l",
        "eng",
    ]
    assert invocation["input"] == b"png bytes"
    assert invocation["timeout"] == 2.5
    assert "shell" not in invocation


@pytest.mark.parametrize(
    ("source", "expected"),
    (
        ("-I2O0", "-1200"),
        ("+5O", "+50"),
        ("-lO", "-10"),
        ("1200", "1200"),
        ("-OO", "-OO"),
        ("-012", "-012"),
        ("-12O.0", "-12O.0"),
        ("PKR -I2O0", "PKR -I2O0"),
        ("O", "O"),
        ("-S0", "-S0"),
    ),
)
def test_amount_normalization_only_returns_valid_unambiguous_integer_tokens(
    source: str,
    expected: str,
) -> None:
    assert normalize_ocr_amount_token(source) == expected


def test_image_only_fixture_has_no_text_layer_and_parses_through_real_local_ocr() -> None:
    original = IMAGE_ONLY_FIXTURE.read_bytes()
    original_hash = sha256(original).hexdigest()
    with fitz.open(stream=original, filetype="pdf") as document:
        assert document.page_count == 1
        assert document[0].get_text().strip() == ""
        assert document[0].get_images(full=True)

    transaction = SyntheticAedTabularPdfParser().parse(original)[0]

    assert transaction.date_text == "2026-01-15"
    assert transaction.description_text == "OCR TEST MARKET"
    assert transaction.amount_text == "-1200"
    assert transaction.currency_text == "AED"
    assert transaction.source_page == 1
    assert transaction.source_row == 1
    assert transaction.extraction_confidence < 1.0
    assert transaction.extraction_method == "ocr:tesseract"
    assert transaction.source_text is not None
    assert "OCR TEST MARKET" in transaction.source_text
    assert sha256(original).hexdigest() == original_hash


def test_registry_selects_the_synthetic_parser_for_its_image_only_fixture() -> None:
    registry = ParserRegistry([SyntheticAedTabularPdfParser()])

    selected = registry.select(
        IMAGE_ONLY_FIXTURE.read_bytes(),
        IMAGE_ONLY_FIXTURE.name,
    )

    assert selected.parser_id == "synthetic-aed-tabular-pdf"


def test_api_container_installs_the_free_local_tesseract_package() -> None:
    dockerfile = (REPOSITORY_ROOT / "apps/api/Dockerfile").read_text(encoding="utf-8")

    assert "apt-get install -y --no-install-recommends tesseract-ocr" in dockerfile
    assert "rm -rf /var/lib/apt/lists/*" in dockerfile
