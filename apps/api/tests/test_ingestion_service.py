from __future__ import annotations

import json
import multiprocessing
import os
import resource
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path
from threading import Event

import fitz
import pytest
from spend_memory.ingestion import registry as registry_module
from spend_memory.ingestion.base import ParsedRawTransaction
from spend_memory.ingestion.parsers.canonical_csv import CanonicalCsvParser
from spend_memory.ingestion.parsers.synthetic_pdf_a import (
    SyntheticAedTabularPdfParser,
)
from spend_memory.ingestion.parsers.synthetic_pdf_b import (
    SyntheticPkrCompactPdfParser,
)
from spend_memory.ingestion.registry import (
    ParserErrorCode,
    ParserRegistry,
    StatementParserError,
)
from spend_memory.ingestion.service import IngestionService
from spend_memory.storage.repository import (
    ImportLimits,
    ImportRepository,
    ImportRepositoryError,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIRECTORY = REPOSITORY_ROOT / "sample_data/source"


class _Parser:
    parser_id = "test-parser"
    version = "1.0"

    def __init__(self) -> None:
        self.detection_calls = 0
        self.parse_calls = 0

    def can_parse(self, document: bytes, filename: str) -> float:
        self.detection_calls += 1
        return 1.0

    def parse(self, document: bytes) -> list[ParsedRawTransaction]:
        self.parse_calls += 1
        return [
            ParsedRawTransaction(
                date_text="2026-01-01",
                description_text="Test purchase",
                amount_text="-1200",
                currency_text="AED",
                source_page=None,
                source_row=2,
                source_text="2026-01-01,Test purchase,-1200",
                extraction_method="delimited_text",
            )
        ]


class _BlockingDetector(_Parser):
    def __init__(self, process_id_path: Path) -> None:
        super().__init__()
        self.process_id_path = process_id_path

    def can_parse(self, document: bytes, filename: str) -> float:
        self.process_id_path.write_text(str(os.getpid()), encoding="utf-8")
        Event().wait()
        return 1.0


class _BlockingParser(_Parser):
    def __init__(self, process_id_path: Path) -> None:
        super().__init__()
        self.process_id_path = process_id_path

    def parse(self, document: bytes) -> list[ParsedRawTransaction]:
        self.process_id_path.write_text(str(os.getpid()), encoding="utf-8")
        Event().wait()
        return []


class _ManyTransactionsParser(_Parser):
    def __init__(self, transaction_count: int) -> None:
        super().__init__()
        self.transaction_count = transaction_count

    def parse(self, document: bytes) -> list[ParsedRawTransaction]:
        return [_Parser.parse(self, document)[0] for _ in range(self.transaction_count)]


class _MemoryExhaustedParser(_Parser):
    def parse(self, document: bytes) -> list[ParsedRawTransaction]:
        raise MemoryError


class _MemoryExhaustedDetector(_Parser):
    def can_parse(self, document: bytes, filename: str) -> float:
        raise MemoryError


class _ResourceReportingParser(_Parser):
    def __init__(self, report_path: Path) -> None:
        super().__init__()
        self.report_path = report_path

    def can_parse(self, document: bytes, filename: str) -> float:
        limit_names = {
            "cpu": resource.RLIMIT_CPU,
            "open_files": resource.RLIMIT_NOFILE,
        }
        if hasattr(resource, "RLIMIT_AS"):
            limit_names["address_space"] = resource.RLIMIT_AS
        self.report_path.write_text(
            json.dumps(
                {
                    name: resource.getrlimit(limit_type)[0]
                    for name, limit_type in limit_names.items()
                }
            ),
            encoding="utf-8",
        )
        return 1.0


class _StatefulParser(_Parser):
    def __init__(self) -> None:
        super().__init__()
        self.detected = False

    def can_parse(self, document: bytes, filename: str) -> float:
        self.detected = True
        return 1.0

    def parse(self, document: bytes) -> list[ParsedRawTransaction]:
        if not self.detected:
            raise RuntimeError("detector state was lost")
        return super().parse(document)


class _BlockingDescendantParser(_Parser):
    def __init__(
        self,
        worker_id_path: Path,
        descendant_id_path: Path,
    ) -> None:
        super().__init__()
        self.worker_id_path = worker_id_path
        self.descendant_id_path = descendant_id_path

    def parse(self, document: bytes) -> list[ParsedRawTransaction]:
        self.worker_id_path.write_text(str(os.getpid()), encoding="utf-8")
        descendant_ready_path = self.descendant_id_path.with_suffix(".ready")
        descendant = subprocess.Popen(
            [
                sys.executable,
                "-c",
                (
                    "import signal,sys,time;"
                    "signal.signal(signal.SIGTERM, signal.SIG_IGN);"
                    "open(sys.argv[1], 'w').write('ready');"
                    "time.sleep(60)"
                ),
                str(descendant_ready_path),
            ]
        )
        self.descendant_id_path.write_text(str(descendant.pid), encoding="utf-8")
        ready_deadline = time.monotonic() + 5
        while not descendant_ready_path.exists():
            if time.monotonic() >= ready_deadline:
                raise RuntimeError("descendant did not start")
            time.sleep(0.01)
        descendant.wait()
        return []


class _CrashingDetector(_Parser):
    def can_parse(self, document: bytes, filename: str) -> float:
        os._exit(17)


class _CrashingParser(_Parser):
    def parse(self, document: bytes) -> list[ParsedRawTransaction]:
        os._exit(17)


class _UnpicklableParser(_Parser):
    def __init__(self) -> None:
        super().__init__()
        self.callback = lambda: None


def _service(
    tmp_path: Path,
    parser: _Parser,
    *,
    max_bytes: int = 1024,
    parser_timeout_seconds: float = 20.0,
    max_parsed_transactions: int = 10_000,
    parser_cpu_limit_seconds: int = 25,
    parser_address_space_bytes: int = 1_500 * 1024 * 1024,
    parser_max_open_files: int = 64,
) -> IngestionService:
    repository = ImportRepository(
        database_path=tmp_path / "spend-memory.duckdb",
        data_directory=tmp_path / "data",
        limits=ImportLimits(
            max_document_bytes=max_bytes,
            parser_timeout_seconds=parser_timeout_seconds,
            max_parsed_transactions=max_parsed_transactions,
            parser_cpu_limit_seconds=parser_cpu_limit_seconds,
            parser_address_space_bytes=parser_address_space_bytes,
            parser_max_open_files=parser_max_open_files,
        ),
    )
    return IngestionService(
        repository=repository,
        parser_registry=ParserRegistry([parser]),
    )


def _encrypted_pdf() -> bytes:
    with fitz.open() as pdf:
        pdf.new_page().insert_text((50, 50), "encrypted statement")
        return pdf.tobytes(
            encryption=fitz.PDF_ENCRYPT_AES_256,
            owner_pw="owner-secret",
            user_pw="user-secret",
        )


@pytest.mark.parametrize(
    ("document", "filename", "mime_type", "max_bytes", "expected_code"),
    (
        (b"too large", "statement.csv", "text/csv", 2, "document_too_large"),
        (b"valid text", "../statement.csv", "text/csv", 1024, "unsafe_filename"),
        (
            b"valid text",
            "statement.csv",
            "application/octet-stream",
            1024,
            "unsupported_mime_type",
        ),
        (
            b"valid text",
            "statement.pdf",
            "application/pdf",
            1024,
            "mime_type_mismatch",
        ),
    ),
)
def test_ingress_rejects_unsafe_documents_before_parser_selection(
    tmp_path: Path,
    document: bytes,
    filename: str,
    mime_type: str,
    max_bytes: int,
    expected_code: str,
) -> None:
    parser = _Parser()
    service = _service(tmp_path, parser, max_bytes=max_bytes)

    with pytest.raises(ImportRepositoryError) as caught:
        service.import_document(
            document=document,
            filename=filename,
            declared_mime_type=mime_type,
        )

    assert caught.value.code == expected_code
    assert parser.detection_calls == 0
    assert parser.parse_calls == 0


def test_ingress_selects_parser_only_after_validation_and_persists_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser = _Parser()
    service = _service(tmp_path, parser)
    validation_calls = 0
    real_validate_document = service.repository.validate_document

    def count_validation(**kwargs) -> None:
        nonlocal validation_calls
        validation_calls += 1
        real_validate_document(**kwargs)

    monkeypatch.setattr(service.repository, "validate_document", count_validation)

    result = service.import_document(
        document=b"valid text",
        filename="statement.csv",
        declared_mime_type="text/csv",
    )

    assert result.transaction_count == 1
    assert validation_calls == 1


def _assert_process_is_gone(process_id_path: Path) -> None:
    process_id = int(process_id_path.read_text(encoding="utf-8"))
    deadline = time.monotonic() + 1
    while time.monotonic() < deadline:
        try:
            os.kill(process_id, 0)
        except ProcessLookupError:
            return
        time.sleep(0.01)
    pytest.fail(f"process {process_id} is still alive")


def _run_import_in_outer_process(
    tmp_path: Path,
    parser: _Parser,
    parser_timeout_seconds: float,
    result_connection,
) -> None:
    try:
        service = _service(
            tmp_path,
            parser,
            parser_timeout_seconds=parser_timeout_seconds,
        )
        service.import_document(
            document=b"valid text",
            filename="statement.csv",
            declared_mime_type="text/csv",
        )
    except StatementParserError as error:
        payload = ("statement_parser_error", error.code.value)
    except ImportRepositoryError as error:
        payload = ("import_repository_error", error.code)
    except BaseException:  # noqa: BLE001
        payload = ("unexpected_error", None)
    else:
        payload = ("success", None)
    try:
        result_connection.send(payload)
    finally:
        result_connection.close()


def _run_blocking_import(
    tmp_path: Path,
    parser: _Parser,
    entered_path: Path,
    *,
    parser_timeout_seconds: float = 2.0,
) -> tuple[str, str | None]:
    process_context = multiprocessing.get_context("spawn")
    receive_result, send_result = process_context.Pipe(duplex=False)
    outer_process = process_context.Process(
        target=_run_import_in_outer_process,
        args=(
            tmp_path,
            parser,
            parser_timeout_seconds,
            send_result,
        ),
    )
    try:
        outer_process.start()
        send_result.close()
        entered_deadline = time.monotonic() + 5
        while not entered_path.exists() and not receive_result.poll():
            if time.monotonic() >= entered_deadline:
                break
            time.sleep(0.01)
        assert entered_path.exists(), "blocking parser did not start"
        outer_process.join(timeout=5)
        if outer_process.is_alive():
            outer_process.terminate()
            outer_process.join(timeout=0.1)
        if outer_process.is_alive():
            outer_process.kill()
            outer_process.join(timeout=0.1)
        assert not outer_process.is_alive(), "outer import process did not stop"
        assert outer_process.exitcode == 0
        assert receive_result.poll()
        return receive_result.recv()
    finally:
        send_result.close()
        receive_result.close()
        if outer_process.is_alive():
            outer_process.kill()
            outer_process.join(timeout=0.1)
        if not outer_process.is_alive():
            outer_process.close()


def test_ingress_kills_a_blocked_detector_at_the_parser_deadline(
    tmp_path: Path,
) -> None:
    process_id_path = tmp_path / "detector.pid"

    started_at = time.monotonic()
    error_type, error_code = _run_blocking_import(
        tmp_path,
        _BlockingDetector(process_id_path),
        process_id_path,
    )

    assert error_type == "statement_parser_error"
    assert error_code == ParserErrorCode.TIME_LIMIT.value
    assert time.monotonic() - started_at < 5
    _assert_process_is_gone(process_id_path)


def test_ingress_kills_a_blocked_parser_at_the_parser_deadline(
    tmp_path: Path,
) -> None:
    process_id_path = tmp_path / "parser.pid"
    started_at = time.monotonic()
    error_type, error_code = _run_blocking_import(
        tmp_path,
        _BlockingParser(process_id_path),
        process_id_path,
    )

    assert error_type == "import_repository_error"
    assert error_code == "time_limit"
    assert time.monotonic() - started_at < 5
    _assert_process_is_gone(process_id_path)


def test_ingress_rejects_a_parser_result_above_the_transaction_limit(
    tmp_path: Path,
) -> None:
    service = _service(
        tmp_path,
        _ManyTransactionsParser(transaction_count=3),
        max_parsed_transactions=2,
    )

    with pytest.raises(ImportRepositoryError) as caught:
        service.import_document(
            document=b"valid text",
            filename="statement.csv",
            declared_mime_type="text/csv",
        )

    assert caught.value.code == "transaction_limit"
    assert str(caught.value) == "transaction_limit"


def test_ingress_returns_a_safe_error_for_a_worker_memory_limit_breach(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path, _MemoryExhaustedParser())

    with pytest.raises(ImportRepositoryError) as caught:
        service.import_document(
            document=b"valid text",
            filename="statement.csv",
            declared_mime_type="text/csv",
        )

    assert caught.value.code == "resource_limit"
    assert str(caught.value) == "resource_limit"


def test_ingress_returns_a_safe_error_for_a_detector_memory_limit_breach(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path, _MemoryExhaustedDetector())

    with pytest.raises(StatementParserError) as caught:
        service.import_document(
            document=b"valid text",
            filename="statement.csv",
            declared_mime_type="text/csv",
        )

    assert caught.value.code is ParserErrorCode.RESOURCE_LIMIT
    assert str(caught.value) == "resource_limit"


def test_isolated_parser_applies_resource_limits_before_detection(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "worker-limits.json"
    service = _service(
        tmp_path,
        _ResourceReportingParser(report_path),
        parser_cpu_limit_seconds=10,
        parser_address_space_bytes=768 * 1024 * 1024,
        parser_max_open_files=48,
    )

    result = service.import_document(
        document=b"valid text",
        filename="statement.csv",
        declared_mime_type="text/csv",
    )

    worker_limits = json.loads(report_path.read_text(encoding="utf-8"))
    assert result.transaction_count == 1
    assert worker_limits["cpu"] <= 10
    assert worker_limits["open_files"] <= 48
    if sys.platform.startswith("linux"):
        assert worker_limits["address_space"] <= 768 * 1024 * 1024


def test_ingress_kills_parser_descendants_at_the_parser_deadline(
    tmp_path: Path,
) -> None:
    worker_id_path = tmp_path / "worker.pid"
    descendant_id_path = tmp_path / "descendant.pid"
    descendant_ready_path = descendant_id_path.with_suffix(".ready")
    parser = _BlockingDescendantParser(
        worker_id_path,
        descendant_id_path,
    )
    error_type, error_code = _run_blocking_import(
        tmp_path,
        parser,
        descendant_ready_path,
    )

    assert error_type == "import_repository_error"
    assert error_code == "time_limit"
    _assert_process_is_gone(worker_id_path)
    _assert_process_is_gone(descendant_id_path)


def test_isolated_parser_preserves_detector_state_through_parse() -> None:
    registry = ParserRegistry([_StatefulParser()])

    parser = registry.select_isolated(
        b"valid text",
        "statement.csv",
        timeout_seconds=5,
    )
    transactions = parser.parse(b"valid text")

    assert len(transactions) == 1


def test_result_reconstruction_cannot_return_success_after_the_deadline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result_path = tmp_path / "parse.json"
    transaction = _Parser().parse(b"valid text")[0]
    result_path.write_text(
        "\n".join(
            (
                json.dumps({"status": "parsed"}),
                json.dumps(asdict(transaction)),
                "",
            )
        ),
        encoding="utf-8",
    )
    clock_values = iter((0.0, 0.0, 0.0, 2.0))
    monkeypatch.setattr(
        registry_module,
        "monotonic",
        lambda: next(clock_values, 2.0),
    )

    with pytest.raises(StatementParserError) as caught:
        registry_module._decode_transactions(result_path, deadline=1.0)

    assert caught.value.code is ParserErrorCode.TIME_LIMIT


def test_ingress_maps_a_crashed_detector_to_a_safe_malformed_error(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path, _CrashingDetector())

    with pytest.raises(StatementParserError) as caught:
        service.import_document(
            document=b"valid text",
            filename="statement.csv",
            declared_mime_type="text/csv",
        )

    assert caught.value.code is ParserErrorCode.MALFORMED
    assert str(caught.value) == "malformed"
    assert caught.value.__cause__ is None


def test_ingress_maps_a_crashed_parser_to_a_safe_malformed_error(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path, _CrashingParser())

    with pytest.raises(ImportRepositoryError) as caught:
        service.import_document(
            document=b"valid text",
            filename="statement.csv",
            declared_mime_type="text/csv",
        )

    assert caught.value.code == "malformed"
    assert str(caught.value) == "malformed"
    assert caught.value.__cause__ is None


def test_isolated_registry_rejects_an_unserializable_parser_safely() -> None:
    registry = ParserRegistry([_UnpicklableParser()])

    with pytest.raises(StatementParserError) as caught:
        registry.select_isolated(
            b"valid text",
            "statement.csv",
            timeout_seconds=5,
        )

    assert caught.value.code is ParserErrorCode.MALFORMED
    assert caught.value.__cause__ is None


@pytest.mark.parametrize(
    ("filename", "expected_transaction_count"),
    (
        ("aed_january_2026.csv", 18),
        ("aed_statement_tabular.pdf", 414),
        ("pkr_statement_compact.pdf", 432),
        ("aed_statement_image_only.pdf", 1),
    ),
)
def test_isolated_parser_boundary_preserves_csv_pdf_and_ocr_results(
    filename: str,
    expected_transaction_count: int,
) -> None:
    document = (SOURCE_DIRECTORY / filename).read_bytes()
    registry = ParserRegistry(
        [
            CanonicalCsvParser(),
            SyntheticAedTabularPdfParser(),
            SyntheticPkrCompactPdfParser(),
        ]
    )

    parser = registry.select_isolated(document, filename, timeout_seconds=20)
    transactions = parser.parse(document)

    assert len(transactions) == expected_transaction_count
    assert all(isinstance(transaction, ParsedRawTransaction) for transaction in transactions)


def test_ingress_classifies_a_real_encrypted_pdf_before_parser_selection(
    tmp_path: Path,
) -> None:
    parser = _Parser()
    service = _service(tmp_path, parser, max_bytes=20 * 1024 * 1024)

    with pytest.raises(ImportRepositoryError) as caught:
        service.import_document(
            document=_encrypted_pdf(),
            filename="statement.pdf",
            declared_mime_type="application/pdf",
        )

    assert caught.value.code == "encrypted"
    assert parser.detection_calls == 0


def test_ingress_enforces_pdf_geometry_before_parser_selection(
    tmp_path: Path,
) -> None:
    parser = _Parser()
    repository = ImportRepository(
        database_path=tmp_path / "spend-memory.duckdb",
        data_directory=tmp_path / "data",
        limits=ImportLimits(
            max_document_bytes=20 * 1024 * 1024,
            max_pdf_page_width_points=600,
            max_pdf_page_height_points=900,
        ),
    )
    service = IngestionService(
        repository=repository,
        parser_registry=ParserRegistry([parser]),
    )
    with fitz.open() as pdf:
        pdf.new_page(width=601, height=842)
        document = pdf.tobytes()

    with pytest.raises(ImportRepositoryError) as caught:
        service.import_document(
            document=document,
            filename="statement.pdf",
            declared_mime_type="application/pdf",
        )

    assert caught.value.code == "pdf_page_dimensions"
    assert parser.detection_calls == 0


def test_ingress_enforces_pdf_preflight_deadline_before_parser_selection(
    tmp_path: Path,
) -> None:
    parser = _Parser()
    repository = ImportRepository(
        database_path=tmp_path / "spend-memory.duckdb",
        data_directory=tmp_path / "data",
        limits=ImportLimits(
            max_document_bytes=20 * 1024 * 1024,
            pdf_preflight_timeout_seconds=0,
        ),
    )
    service = IngestionService(
        repository=repository,
        parser_registry=ParserRegistry([parser]),
    )
    with fitz.open() as pdf:
        pdf.new_page()
        document = pdf.tobytes()

    with pytest.raises(ImportRepositoryError) as caught:
        service.import_document(
            document=document,
            filename="statement.pdf",
            declared_mime_type="application/pdf",
        )

    assert caught.value.code == "pdf_preflight_timeout"
    assert parser.detection_calls == 0


def test_ingress_pdf_preflight_has_a_killable_wall_time_deadline(
    tmp_path: Path,
) -> None:
    parser = _Parser()
    repository = ImportRepository(
        database_path=tmp_path / "spend-memory.duckdb",
        data_directory=tmp_path / "data",
        limits=ImportLimits(
            max_document_bytes=20 * 1024 * 1024,
            pdf_preflight_timeout_seconds=0.01,
        ),
    )
    service = IngestionService(
        repository=repository,
        parser_registry=ParserRegistry([parser]),
    )
    with fitz.open() as pdf:
        pdf.new_page()
        document = pdf.tobytes()

    with pytest.raises(ImportRepositoryError) as caught:
        service.import_document(
            document=document,
            filename="statement.pdf",
            declared_mime_type="application/pdf",
        )

    assert caught.value.code == "pdf_preflight_timeout"
    assert parser.detection_calls == 0
