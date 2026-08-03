import csv
from io import StringIO
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from spend_memory.api.contracts import TransactionFilters
from spend_memory.api.dependencies import get_enrichment_repository
from spend_memory.api.errors import ApiError
from spend_memory.api.routes.transactions import filtered_rows, query_from, sorted_rows
from spend_memory.enrichment.repository import EnrichmentRepository

router = APIRouter()

_COLUMNS = (
    "transaction_id", "transaction_date", "account", "description", "currency",
    "amount_minor", "direction", "merchant", "category", "counterparty", "state",
    "source_document", "source_ordinal", "source_page", "source_row", "source_text",
)


@router.get("/exports/transactions.csv")
def export_transactions(
    filters: Annotated[TransactionFilters, Depends()],
    repository: Annotated[EnrichmentRepository, Depends(get_enrichment_repository)],
) -> Response:
    try:
        rows = sorted_rows(
            filtered_rows(repository.list_search_rows(), query_from(filters), include_all=True),
            filters,
        )
    except RuntimeError:
        raise ApiError("trusted_records_unavailable", "Trusted records are not ready.", 503) from None
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(_COLUMNS)
    for row in rows:
        transaction = row.transaction
        writer.writerow(
            _safe_cell(value)
            for value in (
                transaction.raw_transaction_id, transaction.transaction_date,
                transaction.account_identity, transaction.description, transaction.currency,
                transaction.amount_minor, transaction.direction, row.merchant_name,
                row.category.category_label, row.counterparty_label, row.state,
                row.source_document, row.source_ordinal, row.source_page, row.source_row,
                row.source_text,
            )
        )
    return Response(
        output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=transactions.csv"},
    )


def _safe_cell(value: object | None) -> str:
    cell = "" if value is None else str(value)
    return f"'{cell}" if cell.startswith(("=", "+", "-", "@")) else cell
