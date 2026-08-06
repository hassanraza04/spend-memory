from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from spend_memory.ingestion.registry import ParserRegistry, StatementParserError
from spend_memory.storage.repository import (
    ImportRepository,
    ImportRepositoryError,
    ImportResult,
)


@dataclass(frozen=True)
class IngestionService:
    """Safe public ingress that validates documents before parser selection.

    Callers retrying a known parser result provide both ``parser_id`` and
    ``parser_version``. The service can then return an exact stored run before
    it starts an isolated parser worker.
    """

    repository: ImportRepository
    parser_registry: ParserRegistry

    def import_document(
        self,
        *,
        document: bytes,
        filename: str,
        declared_mime_type: str,
        parser_id: str | None = None,
        parser_version: str | None = None,
    ) -> ImportResult:
        self.repository.validate_document(
            document=document,
            filename=filename,
            declared_mime_type=declared_mime_type,
        )
        if (parser_id is None) != (parser_version is None):
            raise ImportRepositoryError("invalid_parser_identity")
        if parser_id is not None and parser_version is not None:
            existing = self.repository.find_existing_import(
                document=document,
                filename=filename,
                declared_mime_type=declared_mime_type,
                parser_id=parser_id,
                parser_version=parser_version,
            )
            if existing is not None:
                return existing
        parser = self.parser_registry.select_isolated(
            document,
            filename,
            timeout_seconds=self.repository.limits.parser_timeout_seconds,
            max_parsed_transactions=self.repository.limits.max_parsed_transactions,
            worker_cpu_limit_seconds=self.repository.limits.parser_cpu_limit_seconds,
            worker_address_space_bytes=self.repository.limits.parser_address_space_bytes,
            worker_max_open_files=self.repository.limits.parser_max_open_files,
        )
        try:
            if (
                parser_id is not None
                and (parser.parser_id != parser_id or parser.version != parser_version)
            ):
                raise ImportRepositoryError("parser_identity_mismatch")
            transactions = parser.parse(document)
            return self.repository.store_preparsed_document(
                document=document,
                filename=filename,
                declared_mime_type=declared_mime_type,
                parser_id=parser.parser_id,
                parser_version=parser.version,
                transactions=transactions,
            )
        except StatementParserError as error:
            self.repository.record_isolated_parse_error(
                document=document,
                filename=filename,
                declared_mime_type=declared_mime_type,
                parser_id=parser.parser_id,
                parser_version=parser.version,
                code=error.code.value,
            )
            raise ImportRepositoryError(error.code.value) from None
        finally:
            parser.close()

    def reprocess_document(self, document_id: UUID) -> ImportResult:
        stored = self.repository.read_document_for_reprocess(document_id)
        if stored is None:
            raise ImportRepositoryError("import_not_found")
        document, filename, mime_type = stored
        return self.import_document(
            document=document,
            filename=filename,
            declared_mime_type=mime_type,
        )

    def inspect_document(self, document_id: UUID):
        return self.repository.inspect_document(document_id)
