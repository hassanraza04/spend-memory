from __future__ import annotations

from dataclasses import dataclass

from spend_memory.ingestion.registry import ParserRegistry
from spend_memory.storage.repository import ImportRepository, ImportResult


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
            return self.repository._import_prevalidated_document(
                document=document,
                filename=filename,
                declared_mime_type=declared_mime_type,
                parser=parser,
            )
        finally:
            parser.close()
