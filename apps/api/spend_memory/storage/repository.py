from __future__ import annotations

import fcntl
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from threading import Lock
from uuid import UUID, uuid4
from weakref import WeakValueDictionary

import duckdb
import fitz

from spend_memory.ingestion.base import StatementParser


@dataclass(frozen=True)
class ImportResult:
    document_id: UUID
    run_id: UUID
    transaction_count: int
    was_already_imported: bool


@dataclass(frozen=True)
class ImportLimits:
    max_document_bytes: int = 20 * 1024 * 1024
    max_pdf_pages: int = 20


DEFAULT_IMPORT_LIMITS = ImportLimits()
_IMPORT_GATES = WeakValueDictionary()
_IMPORT_GATES_LOCK = Lock()


@contextmanager
def _import_gate(key: tuple[str, str, str]) -> Iterator[None]:
    with _IMPORT_GATES_LOCK:
        gate = _IMPORT_GATES.get(key)
        if gate is None:
            gate = Lock()
            _IMPORT_GATES[key] = gate
    with gate:
        yield


@contextmanager
def _document_file_lock(
    data_directory: Path,
    document_sha256: str,
) -> Iterator[None]:
    data_directory.mkdir(parents=True, exist_ok=True)
    locks_directory = data_directory / ".locks"
    lock_path = locks_directory / f"{document_sha256}.lock"
    directory_fd = os.open(data_directory, os.O_RDONLY)
    document_lock_fd: int | None = None

    try:
        while document_lock_fd is None:
            fcntl.flock(directory_fd, fcntl.LOCK_EX)
            candidate_fd: int | None = None
            try:
                locks_directory.mkdir(mode=0o700, exist_ok=True)
                candidate_fd = os.open(
                    lock_path,
                    os.O_RDWR | os.O_CREAT,
                    0o600,
                )
                try:
                    fcntl.flock(
                        candidate_fd,
                        fcntl.LOCK_EX | fcntl.LOCK_NB,
                    )
                except BlockingIOError:
                    os.close(candidate_fd)
                else:
                    document_lock_fd = candidate_fd
            finally:
                fcntl.flock(directory_fd, fcntl.LOCK_UN)

            if document_lock_fd is None:
                time.sleep(0.01)

        yield
    finally:
        if document_lock_fd is not None:
            fcntl.flock(directory_fd, fcntl.LOCK_EX)
            try:
                try:
                    artifact_stat = lock_path.stat(follow_symlinks=False)
                except FileNotFoundError:
                    pass
                else:
                    lock_stat = os.fstat(document_lock_fd)
                    if (
                        artifact_stat.st_dev == lock_stat.st_dev
                        and artifact_stat.st_ino == lock_stat.st_ino
                    ):
                        lock_path.unlink()

                fcntl.flock(document_lock_fd, fcntl.LOCK_UN)
                os.close(document_lock_fd)
                document_lock_fd = None
                try:
                    locks_directory.rmdir()
                except OSError:
                    pass
            finally:
                if document_lock_fd is not None:
                    fcntl.flock(document_lock_fd, fcntl.LOCK_UN)
                    os.close(document_lock_fd)
                fcntl.flock(directory_fd, fcntl.LOCK_UN)
        os.close(directory_fd)


class ImportRepositoryError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def apply_migrations(
    database_path: Path,
    *,
    migration_directory: Path | None = None,
) -> None:
    """Apply each bundled migration once in one transaction."""
    database_path.parent.mkdir(parents=True, exist_ok=True)
    storage_directory = Path(__file__).parent
    migration_directory = migration_directory or storage_directory / "migrations"

    with duckdb.connect(str(database_path)) as connection:
        connection.execute("BEGIN TRANSACTION")
        try:
            connection.execute(
                (storage_directory / "schema.sql").read_text(encoding="utf-8")
            )
            applied = {
                row[0]
                for row in connection.execute(
                    "SELECT version FROM storage_migrations"
                ).fetchall()
            }
            for migration_path in sorted(migration_directory.glob("*.sql")):
                if migration_path.stem in applied:
                    continue
                connection.execute(migration_path.read_text(encoding="utf-8"))
                connection.execute(
                    "INSERT INTO storage_migrations (version) VALUES (?)",
                    [migration_path.stem],
                )
            connection.execute("COMMIT")
        except BaseException:
            connection.execute("ROLLBACK")
            raise


class ImportRepository:
    def __init__(
        self,
        *,
        database_path: Path,
        data_directory: Path,
        limits: ImportLimits = DEFAULT_IMPORT_LIMITS,
    ) -> None:
        self.database_path = Path(database_path)
        self.data_directory = Path(data_directory)
        self.limits = limits
        apply_migrations(self.database_path)

    def import_document(
        self,
        *,
        document: bytes,
        filename: str,
        declared_mime_type: str,
        parser: StatementParser,
    ) -> ImportResult:
        if (
            not filename
            or filename in {".", ".."}
            or "/" in filename
            or "\\" in filename
            or "\0" in filename
        ):
            raise ImportRepositoryError("unsafe_filename")
        if len(document) > self.limits.max_document_bytes:
            raise ImportRepositoryError("document_too_large")
        if declared_mime_type not in {"application/pdf", "text/csv"}:
            raise ImportRepositoryError("unsupported_mime_type")
        if declared_mime_type == "text/csv" and (
            document.startswith(b"%PDF-") or not _is_text_document(document)
        ):
            raise ImportRepositoryError("mime_type_mismatch")
        if declared_mime_type == "application/pdf" and not document.startswith(
            b"%PDF-"
        ):
            raise ImportRepositoryError("mime_type_mismatch")
        if declared_mime_type == "application/pdf":
            self._validate_pdf(document)
        document_sha256 = sha256(document).hexdigest()
        storage_filename = f"{document_sha256}{_extension_for(declared_mime_type)}"
        final_path = self.data_directory / storage_filename
        import_key = (
            str(self.database_path.resolve()),
            str(self.data_directory.resolve()),
            document_sha256,
        )

        with (
            _import_gate(import_key),
            _document_file_lock(self.data_directory, document_sha256),
        ):
            return self._import_validated_document(
                document=document,
                filename=filename,
                declared_mime_type=declared_mime_type,
                parser=parser,
                document_sha256=document_sha256,
                storage_filename=storage_filename,
                final_path=final_path,
            )

    def _import_validated_document(
        self,
        *,
        document: bytes,
        filename: str,
        declared_mime_type: str,
        parser: StatementParser,
        document_sha256: str,
        storage_filename: str,
        final_path: Path,
    ) -> ImportResult:
        with duckdb.connect(str(self.database_path)) as connection:
            existing = connection.execute(
                """
                SELECT d.document_id, r.run_id,
                       (SELECT count(*)
                        FROM raw_transactions t
                        WHERE t.import_run_id = r.run_id)
                FROM source_documents d
                JOIN import_runs r ON r.document_id = d.document_id
                WHERE d.sha256_hex = ?
                  AND r.parser_id = ?
                  AND r.parser_version = ?
                """,
                [document_sha256, parser.parser_id, parser.version],
            ).fetchone()
            if existing is not None:
                return ImportResult(
                    document_id=existing[0],
                    run_id=existing[1],
                    transaction_count=existing[2],
                    was_already_imported=True,
                )

        try:
            transactions = parser.parse(document)
        except Exception:  # noqa: BLE001
            self._record_error(
                document_sha256=document_sha256,
                filename=filename,
                declared_mime_type=declared_mime_type,
                parser=parser,
                code="parser_failed",
            )
            raise ImportRepositoryError("parser_failed") from None
        document_id = uuid4()
        run_id = uuid4()
        try:
            staged_path = self._stage_document(document, document_sha256)
        except Exception:  # noqa: BLE001
            self._record_error(
                document_sha256=document_sha256,
                filename=filename,
                declared_mime_type=declared_mime_type,
                parser=parser,
                code="storage_failed",
            )
            raise ImportRepositoryError("storage_failed") from None
        remove_final_file_on_failure = False

        try:
            with duckdb.connect(str(self.database_path)) as connection:
                connection.execute("BEGIN TRANSACTION")
                try:
                    existing_document = connection.execute(
                        """
                        SELECT document_id
                        FROM source_documents
                        WHERE sha256_hex = ?
                        """,
                        [document_sha256],
                    ).fetchone()
                    if existing_document is None:
                        connection.execute(
                            """
                            INSERT INTO source_documents (
                                document_id,
                                sha256_hex,
                                original_filename,
                                mime_type,
                                byte_size,
                                storage_filename
                            )
                            VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            [
                                document_id,
                                document_sha256,
                                filename,
                                declared_mime_type,
                                len(document),
                                storage_filename,
                            ],
                        )
                    else:
                        document_id = existing_document[0]

                    connection.execute(
                        """
                        INSERT INTO import_runs (
                            run_id,
                            document_id,
                            parser_id,
                            parser_version,
                            is_active
                        )
                        VALUES (?, ?, ?, ?, true)
                        """,
                        [
                            run_id,
                            document_id,
                            parser.parser_id,
                            parser.version,
                        ],
                    )
                    connection.execute(
                        """
                        UPDATE import_runs
                        SET is_active = false
                        WHERE document_id = ? AND run_id <> ?
                        """,
                        [document_id, run_id],
                    )
                    for source_ordinal, transaction in enumerate(
                        transactions, start=1
                    ):
                        connection.execute(
                            """
                            INSERT INTO raw_transactions (
                                raw_transaction_id,
                                import_run_id,
                                source_ordinal,
                                date_text,
                                description_text,
                                amount_text,
                                currency_text,
                                source_page,
                                source_row,
                                source_text,
                                extraction_method,
                                raw_account_identity,
                                raw_account_reference,
                                raw_balance_text,
                                extraction_confidence
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            [
                                uuid4(),
                                run_id,
                                source_ordinal,
                                transaction.date_text,
                                transaction.description_text,
                                transaction.amount_text,
                                transaction.currency_text,
                                transaction.source_page,
                                transaction.source_row,
                                transaction.source_text,
                                transaction.extraction_method,
                                transaction.raw_account_identity,
                                transaction.raw_account_reference,
                                transaction.raw_balance_text,
                                transaction.extraction_confidence,
                            ],
                        )

                    if not final_path.exists():
                        remove_final_file_on_failure = True
                        os.replace(staged_path, final_path)
                    connection.execute("COMMIT")
                except BaseException:
                    connection.execute("ROLLBACK")
                    raise
        except BaseException as error:
            if remove_final_file_on_failure:
                final_path.unlink(missing_ok=True)
            if not isinstance(error, Exception):
                raise
            self._record_error(
                document_sha256=document_sha256,
                filename=filename,
                declared_mime_type=declared_mime_type,
                parser=parser,
                code="storage_failed",
            )
            raise ImportRepositoryError("storage_failed") from None
        finally:
            staged_path.unlink(missing_ok=True)

        return ImportResult(
            document_id=document_id,
            run_id=run_id,
            transaction_count=len(transactions),
            was_already_imported=False,
        )

    def _stage_document(self, document: bytes, document_sha256: str) -> Path:
        self.data_directory.mkdir(parents=True, exist_ok=True)
        staged_path = self.data_directory / f".{document_sha256}.{uuid4().hex}.tmp"
        try:
            with staged_path.open("xb") as staged_file:
                staged_path.chmod(0o600)
                staged_file.write(document)
                staged_file.flush()
                os.fsync(staged_file.fileno())
        except BaseException:
            staged_path.unlink(missing_ok=True)
            raise
        return staged_path

    def _record_error(
        self,
        *,
        document_sha256: str,
        filename: str,
        declared_mime_type: str,
        parser: StatementParser,
        code: str,
    ) -> None:
        with duckdb.connect(str(self.database_path)) as connection:
            connection.execute(
                """
                INSERT INTO import_errors (
                    error_id,
                    document_sha256_hex,
                    original_filename,
                    declared_mime_type,
                    parser_id,
                    parser_version,
                    error_type,
                    error_message
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    uuid4(),
                    document_sha256,
                    filename,
                    declared_mime_type,
                    parser.parser_id,
                    parser.version,
                    code,
                    code,
                ],
            )

    def _validate_pdf(self, document: bytes) -> None:
        try:
            with fitz.open(stream=document, filetype="pdf") as pdf:
                if pdf.needs_pass or not pdf.page_count:
                    raise ImportRepositoryError("invalid_pdf")
                if pdf.page_count > self.limits.max_pdf_pages:
                    raise ImportRepositoryError("pdf_page_limit")
        except ImportRepositoryError:
            raise
        except (fitz.FileDataError, RuntimeError, ValueError):
            raise ImportRepositoryError("invalid_pdf") from None


def _extension_for(mime_type: str) -> str:
    return {
        "application/pdf": ".pdf",
        "text/csv": ".csv",
    }[mime_type]


def _is_text_document(document: bytes) -> bool:
    try:
        text = document.decode("utf-8-sig")
    except UnicodeDecodeError:
        return False
    return not any(
        ord(character) < 32 and character not in "\t\r\n" for character in text
    )
