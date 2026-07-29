from __future__ import annotations

from dataclasses import dataclass

from spend_memory.ingestion.registry import ParserRegistry, StatementParserError
from spend_memory.storage.repository import (
    ImportRepository,
    ImportRepositoryError,
    ImportResult,
)


@dataclass(frozen=True)
class IngestionService:
    """Safe public ingress that validates documents before parser selection."""

    repository: ImportRepository
    parser_registry: ParserRegistry

    def import_document(
        self,
        *,
        document: bytes,
        filename: str,
        declared_mime_type: str,
    ) -> ImportResult:
        self.repository.validate_document(
            document=document,
            filename=filename,
            declared_mime_type=declared_mime_type,
        )
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
