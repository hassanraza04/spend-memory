from __future__ import annotations

import json
import multiprocessing
import os
import pickle
import signal
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field, fields
from enum import Enum
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic
from typing import Any

import fitz

from spend_memory.ingestion import resource_limits
from spend_memory.ingestion.base import ParsedRawTransaction, StatementParser


class ParserErrorCode(str, Enum):
    UNSUPPORTED = "unsupported"
    ENCRYPTED = "encrypted"
    MALFORMED = "malformed"
    AMBIGUOUS = "ambiguous"
    TIME_LIMIT = "time_limit"
    TRANSACTION_LIMIT = "transaction_limit"
    RESOURCE_LIMIT = "resource_limit"


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
        _raise_if_encrypted_pdf(document, filename)
        try:
            candidates = [
                (parser.can_parse(document, filename), parser) for parser in self._parsers
            ]
        except StatementParserError:
            raise
        except MemoryError:
            raise StatementParserError(ParserErrorCode.RESOURCE_LIMIT) from None
        except Exception:  # noqa: BLE001
            raise StatementParserError(ParserErrorCode.MALFORMED) from None
        compatible = [
            (confidence, parser) for confidence, parser in candidates if confidence > 0
        ]
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
        except MemoryError:
            raise StatementParserError(ParserErrorCode.RESOURCE_LIMIT) from None
        except Exception:  # noqa: BLE001
            raise StatementParserError(ParserErrorCode.MALFORMED) from None

    def select_isolated(
        self,
        document: bytes,
        filename: str,
        *,
        timeout_seconds: float,
        max_parsed_transactions: int = 10_000,
        worker_cpu_limit_seconds: int = 25,
        worker_address_space_bytes: int = 1_500 * 1024 * 1024,
        worker_max_open_files: int = 64,
    ) -> _IsolatedStatementParser:
        if (
            max_parsed_transactions < 0
            or worker_cpu_limit_seconds <= 0
            or worker_address_space_bytes <= 0
            or worker_max_open_files <= 0
        ):
            raise StatementParserError(ParserErrorCode.MALFORMED)
        worker_resource_limits = resource_limits.ResourceLimits(
            cpu_seconds=worker_cpu_limit_seconds,
            address_space_bytes=worker_address_space_bytes,
            max_open_files=worker_max_open_files,
        )
        deadline = monotonic() + timeout_seconds
        cleanup_reserve_seconds = min(0.25, max(0, timeout_seconds * 0.2))
        work_deadline = deadline - cleanup_reserve_seconds
        if work_deadline <= monotonic():
            raise StatementParserError(ParserErrorCode.TIME_LIMIT)

        parsers = tuple(self._parsers)
        try:
            pickle.dumps(parsers, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception:  # noqa: BLE001
            raise StatementParserError(ParserErrorCode.MALFORMED) from None
        process_context = multiprocessing.get_context("spawn")
        session_ready = process_context.Event()
        selection_ready = process_context.Event()
        parse_ready = process_context.Event()
        receive_command, send_command = process_context.Pipe(duplex=False)
        result_directory = TemporaryDirectory(prefix="spend-memory-parser-")
        selection_path = Path(result_directory.name) / "selection.json"
        parse_path = Path(result_directory.name) / "parse.json"
        worker = process_context.Process(
            target=_parser_worker,
            args=(
                parsers,
                document,
                filename,
                receive_command,
                session_ready,
                selection_ready,
                parse_ready,
                selection_path,
                parse_path,
                max_parsed_transactions,
                worker_resource_limits,
            ),
        )
        handle = _ParserWorkerHandle(
            worker=worker,
            send_command=send_command,
            session_ready=session_ready,
            selection_ready=selection_ready,
            parse_ready=parse_ready,
            selection_path=selection_path,
            parse_path=parse_path,
            result_directory=result_directory,
            deadline=deadline,
            work_deadline=work_deadline,
            max_parsed_transactions=max_parsed_transactions,
        )
        try:
            worker.start()
            receive_command.close()
            _wait_for_worker_result(selection_ready, worker, work_deadline)
            payload = _read_selection_result(selection_path, work_deadline)
            if (
                not isinstance(payload, dict)
                or payload.get("status") != "selected"
                or not isinstance(payload.get("parser_id"), str)
                or not isinstance(payload.get("version"), str)
            ):
                _raise_worker_error(payload)
            return _IsolatedStatementParser(
                parser_id=payload["parser_id"],
                version=payload["version"],
                document_sha256=sha256(document).hexdigest(),
                handle=handle,
            )
        except StatementParserError:
            handle.close()
            raise
        except BaseException:  # noqa: BLE001
            handle.close()
            raise StatementParserError(ParserErrorCode.MALFORMED) from None
        finally:
            receive_command.close()


@dataclass(frozen=True)
class _IsolatedStatementParser:
    parser_id: str
    version: str
    document_sha256: str = field(repr=False, compare=False)
    handle: _ParserWorkerHandle = field(repr=False, compare=False)

    def can_parse(self, document: bytes, filename: str) -> float:
        return 1.0

    def parse(self, document: bytes) -> list[ParsedRawTransaction]:
        if sha256(document).hexdigest() != self.document_sha256:
            self.close()
            raise StatementParserError(ParserErrorCode.MALFORMED)
        return self.handle.parse()

    def close(self) -> None:
        self.handle.close()


@dataclass
class _ParserWorkerHandle:
    worker: Any
    send_command: Any
    session_ready: Any
    selection_ready: Any
    parse_ready: Any
    selection_path: Path
    parse_path: Path
    result_directory: TemporaryDirectory[str]
    deadline: float
    work_deadline: float
    max_parsed_transactions: int
    closed: bool = False

    def parse(self) -> list[ParsedRawTransaction]:
        if self.closed:
            raise StatementParserError(ParserErrorCode.MALFORMED)
        try:
            if monotonic() >= self.work_deadline:
                raise StatementParserError(ParserErrorCode.TIME_LIMIT)
            self.send_command.send_bytes(b"P")
            _wait_for_worker_result(
                self.parse_ready,
                self.worker,
                self.work_deadline,
            )
            return _decode_transactions(
                self.parse_path,
                self.work_deadline,
                max_parsed_transactions=self.max_parsed_transactions,
            )
        finally:
            self.close()

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        if self.worker.is_alive():
            try:
                self.send_command.send_bytes(b"C")
            except (BrokenPipeError, OSError):
                pass
            self.worker.join(timeout=_remaining_seconds(self.work_deadline))
        _stop_worker(
            self.worker,
            session_ready=self.session_ready,
            deadline=self.deadline,
        )
        self.send_command.close()
        self.result_directory.cleanup()


def _parser_worker(
    parsers: tuple[StatementParser, ...],
    document: bytes,
    filename: str,
    command_connection,
    session_ready,
    selection_ready,
    parse_ready,
    selection_path: Path,
    parse_path: Path,
    max_parsed_transactions: int,
    worker_resource_limits: resource_limits.ResourceLimits,
) -> None:
    try:
        os.setsid()
        session_ready.set()
        try:
            resource_limits.apply_resource_limits(worker_resource_limits)
            selected = ParserRegistry(parsers).select(document, filename)
            selection_payload = {
                "status": "selected",
                "parser_id": selected.parser_id,
                "version": selected.version,
            }
        except StatementParserError as error:
            selection_payload = {"status": "error", "code": error.code.value}
            selected = None
        except MemoryError:
            selection_payload = {
                "status": "error",
                "code": ParserErrorCode.RESOURCE_LIMIT.value,
            }
            selected = None
        except BaseException:  # noqa: BLE001
            selection_payload = {
                "status": "error",
                "code": ParserErrorCode.MALFORMED.value,
            }
            selected = None
        _write_worker_result(selection_path, selection_payload)
        selection_ready.set()
        if selected is None:
            return

        try:
            command = command_connection.recv_bytes(1)
        except (EOFError, OSError):
            return
        if command != b"P":
            return
        try:
            transactions = selected.parse(document)
            if not isinstance(transactions, list) or not all(
                isinstance(transaction, ParsedRawTransaction)
                for transaction in transactions
            ):
                raise StatementParserError(ParserErrorCode.MALFORMED)
            if len(transactions) > max_parsed_transactions:
                raise StatementParserError(ParserErrorCode.TRANSACTION_LIMIT)
            _write_transactions(parse_path, transactions)
        except StatementParserError as error:
            _write_worker_result(
                parse_path,
                {"status": "error", "code": error.code.value},
            )
        except MemoryError:
            _write_worker_result(
                parse_path,
                {
                    "status": "error",
                    "code": ParserErrorCode.RESOURCE_LIMIT.value,
                },
            )
        except BaseException:  # noqa: BLE001
            _write_worker_result(
                parse_path,
                {
                    "status": "error",
                    "code": ParserErrorCode.MALFORMED.value,
                },
            )
        parse_ready.set()
    finally:
        command_connection.close()


def _write_worker_result(path: Path, payload: object) -> None:
    try:
        encoded = _encode_json_line(payload)
        if len(encoded) > _MAX_WORKER_RECORD_BYTES:
            raise ValueError
    except (TypeError, ValueError):
        encoded = b'{"status":"error","code":"malformed"}\n'
    path.write_bytes(encoded)


def _write_transactions(
    path: Path,
    transactions: list[ParsedRawTransaction],
) -> None:
    temporary_path = path.with_suffix(".tmp")
    try:
        total_bytes = 0
        with temporary_path.open("wb") as result_file:
            header = _encode_json_line({"status": "parsed"})
            result_file.write(header)
            total_bytes += len(header)
            for transaction in transactions:
                record = _encode_json_line(asdict(transaction))
                if len(record) > _MAX_WORKER_RECORD_BYTES:
                    raise ValueError
                total_bytes += len(record)
                if total_bytes > _MAX_WORKER_RESULT_BYTES:
                    raise ValueError
                result_file.write(record)
        os.replace(temporary_path, path)
    except (TypeError, ValueError):
        temporary_path.unlink(missing_ok=True)
        _write_worker_result(
            path,
            {"status": "error", "code": ParserErrorCode.MALFORMED.value},
        )


def _encode_json_line(payload: object) -> bytes:
    return json.dumps(payload, separators=(",", ":")).encode("utf-8") + b"\n"


def _read_selection_result(path: Path, deadline: float) -> object:
    try:
        if monotonic() >= deadline:
            raise StatementParserError(ParserErrorCode.TIME_LIMIT)
        if path.stat().st_size > _MAX_WORKER_RECORD_BYTES:
            raise StatementParserError(ParserErrorCode.MALFORMED)
        with path.open("rb") as result_file:
            payload = _read_json_line(result_file, deadline)
            if result_file.read(1):
                raise StatementParserError(ParserErrorCode.MALFORMED)
        if monotonic() >= deadline:
            raise StatementParserError(ParserErrorCode.TIME_LIMIT)
        return payload
    except StatementParserError:
        raise
    except BaseException:  # noqa: BLE001
        raise StatementParserError(ParserErrorCode.MALFORMED) from None


def _decode_transactions(
    path: Path,
    deadline: float,
    *,
    max_parsed_transactions: int = 10_000,
) -> list[ParsedRawTransaction]:
    try:
        if monotonic() >= deadline:
            raise StatementParserError(ParserErrorCode.TIME_LIMIT)
        if path.stat().st_size > _MAX_WORKER_RESULT_BYTES:
            raise StatementParserError(ParserErrorCode.MALFORMED)
        result_file = path.open("rb")
        if monotonic() >= deadline:
            raise StatementParserError(ParserErrorCode.TIME_LIMIT)
    except StatementParserError:
        raise
    except BaseException:  # noqa: BLE001
        raise StatementParserError(ParserErrorCode.MALFORMED) from None

    expected_fields = {field.name for field in fields(ParsedRawTransaction)}
    transactions: list[ParsedRawTransaction] = []
    try:
        with result_file:
            header = _read_json_line(result_file, deadline)
            if not isinstance(header, dict) or header.get("status") != "parsed":
                _raise_worker_error(header)
            while True:
                if monotonic() >= deadline:
                    raise StatementParserError(ParserErrorCode.TIME_LIMIT)
                encoded = result_file.readline(_MAX_WORKER_RECORD_BYTES + 1)
                if monotonic() >= deadline:
                    raise StatementParserError(ParserErrorCode.TIME_LIMIT)
                if not encoded:
                    break
                transaction = _decode_json_line(encoded, deadline)
                if (
                    not isinstance(transaction, dict)
                    or set(transaction) != expected_fields
                ):
                    raise StatementParserError(ParserErrorCode.MALFORMED)
                try:
                    transactions.append(ParsedRawTransaction(**transaction))
                except (TypeError, ValueError):
                    raise StatementParserError(ParserErrorCode.MALFORMED) from None
                if len(transactions) > max_parsed_transactions:
                    raise StatementParserError(ParserErrorCode.TRANSACTION_LIMIT)
                if monotonic() >= deadline:
                    raise StatementParserError(ParserErrorCode.TIME_LIMIT)
        if monotonic() >= deadline:
            raise StatementParserError(ParserErrorCode.TIME_LIMIT)
        return transactions
    except StatementParserError:
        raise
    except BaseException:  # noqa: BLE001
        raise StatementParserError(ParserErrorCode.MALFORMED) from None


def _read_json_line(result_file, deadline: float) -> object:
    if monotonic() >= deadline:
        raise StatementParserError(ParserErrorCode.TIME_LIMIT)
    encoded = result_file.readline(_MAX_WORKER_RECORD_BYTES + 1)
    return _decode_json_line(encoded, deadline)


def _decode_json_line(encoded: bytes, deadline: float) -> object:
    if (
        not encoded
        or len(encoded) > _MAX_WORKER_RECORD_BYTES
        or not encoded.endswith(b"\n")
    ):
        raise StatementParserError(ParserErrorCode.MALFORMED)
    try:
        payload = json.loads(encoded)
    except BaseException:  # noqa: BLE001
        raise StatementParserError(ParserErrorCode.MALFORMED) from None
    if monotonic() >= deadline:
        raise StatementParserError(ParserErrorCode.TIME_LIMIT)
    return payload


def _stop_worker(worker, *, session_ready, deadline: float) -> None:
    session_was_ready = session_ready.is_set()
    if session_was_ready:
        _signal_process_group(worker.pid, signal.SIGTERM)
    elif worker.is_alive():
        worker.terminate()
    if worker.is_alive():
        remaining_seconds = _remaining_seconds(deadline)
        worker.join(timeout=min(0.1, remaining_seconds))
    if session_was_ready:
        _signal_process_group(worker.pid, signal.SIGKILL)
    elif worker.is_alive():
        worker.kill()
    if worker.is_alive():
        worker.join(timeout=_remaining_seconds(deadline))
    if not worker.is_alive():
        worker.close()


def _signal_process_group(process_group_id: int, signal_number: int) -> None:
    try:
        os.killpg(process_group_id, signal_number)
    except ProcessLookupError:
        pass


def _remaining_seconds(deadline: float) -> float:
    return max(0, deadline - monotonic())


def _wait_for_worker_result(result_ready, worker, deadline: float) -> None:
    while True:
        remaining_seconds = _remaining_seconds(deadline)
        if remaining_seconds <= 0:
            raise StatementParserError(ParserErrorCode.TIME_LIMIT)
        if result_ready.wait(min(0.01, remaining_seconds)):
            return
        if not worker.is_alive():
            raise _worker_exit_error(worker)


def _worker_exit_error(worker) -> StatementParserError:
    resource_signals = {
        -signal_number
        for signal_number in (
            getattr(signal, "SIGXCPU", None),
            getattr(signal, "SIGKILL", None),
        )
        if signal_number is not None
    }
    if worker.exitcode in resource_signals:
        return StatementParserError(ParserErrorCode.RESOURCE_LIMIT)
    return StatementParserError(ParserErrorCode.MALFORMED)


def _raise_worker_error(payload: object) -> None:
    if (
        isinstance(payload, dict)
        and payload.get("status") == "error"
        and isinstance(payload.get("code"), str)
    ):
        try:
            code = ParserErrorCode(payload["code"])
        except ValueError:
            pass
        else:
            raise StatementParserError(code)
    raise StatementParserError(ParserErrorCode.MALFORMED)


_MAX_WORKER_RECORD_BYTES = 1024 * 1024
_MAX_WORKER_RESULT_BYTES = 64 * _MAX_WORKER_RECORD_BYTES


def _raise_if_encrypted_pdf(document: bytes, filename: str) -> None:
    if not filename.lower().endswith(".pdf") or not document.startswith(b"%PDF-"):
        return
    try:
        with fitz.open(stream=document, filetype="pdf") as pdf:
            if pdf.needs_pass:
                raise StatementParserError(ParserErrorCode.ENCRYPTED)
    except StatementParserError:
        raise
    except (fitz.FileDataError, RuntimeError, ValueError):
        return
