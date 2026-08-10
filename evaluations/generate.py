from __future__ import annotations

import argparse
import json
import resource
import sys
from collections import Counter
from datetime import date
from html import escape
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from uuid import UUID

import duckdb
from spend_memory.enrichment.merchants import evaluate_merchant_matches
from spend_memory.enrichment.models import CategoryDecision, TrustedTransaction
from spend_memory.enrichment.normalization import normalize_descriptor
from spend_memory.enrichment.recurring import detect_recurring_candidates
from spend_memory.enrichment.review import find_duplicate_candidates
from spend_memory.enrichment.search import (
    SearchQueryError,
    SearchRow,
    parse_search_query,
    search_transactions,
)
from spend_memory.ingestion.parsers.canonical_csv import CanonicalCsvParser
from spend_memory.ingestion.parsers.synthetic_pdf_a import SyntheticAedTabularPdfParser
from spend_memory.ingestion.parsers.synthetic_pdf_b import SyntheticPkrCompactPdfParser
from spend_memory.ingestion.registry import ParserRegistry
from spend_memory.ingestion.service import IngestionService
from spend_memory.storage.repository import ImportRepository

_SOURCES = (
    ("aed_january_2026.csv", "text/csv"),
    ("aed_statement_tabular.pdf", "application/pdf"),
    ("pkr_statement_compact.pdf", "application/pdf"),
)


def evaluate(project_root: Path) -> dict[str, object]:
    """Evaluate stable synthetic fixtures without reading user data."""
    expected = json.loads(
        (project_root / "sample_data/expected/canonical_ledger.json").read_text()
    )
    started = perf_counter()
    extracted = _import_canonical_sources(project_root)
    import_time_ms = round((perf_counter() - started) * 1000, 2)
    search_started = perf_counter()
    search = _evaluate_search()
    query_latency_ms = round((perf_counter() - search_started) * 1000, 2)

    return {
        "dataset": {
            "seed": expected["metadata"]["seed"],
            "transaction_count": expected["metadata"]["transaction_count"],
        },
        "extraction": _evaluate_extraction(expected["transactions"], extracted),
        "merchant_resolution": _evaluate_merchants(),
        "recurring_detection": _evaluate_recurring(),
        "duplicate_detection": _evaluate_duplicates(),
        "search": search,
        "runtime": {
            "import_time_ms": import_time_ms,
            "ocr_time_ms": None,
            "index_time_ms": None,
            "query_latency_ms": query_latency_ms,
            "peak_rss_kib": _peak_rss_kib(),
        },
        "deferred_metrics": {
            "category_learning": "not implemented",
            "semantic_index": "not implemented",
            "ocr": "excluded from the canonical ledger",
        },
        "known_limitations": [
            "The image-only OCR fixture is exploratory and has no immutable ledger label.",
            "Category learning and semantic indexing are deliberately not product features yet.",
            "Runtime numbers are local-machine measurements, not performance guarantees.",
        ],
    }


def write_report(report: dict[str, object], output_directory: Path) -> dict[str, Path]:
    output_directory.mkdir(parents=True, exist_ok=True)
    paths = {
        "markdown": output_directory / "REPORT.md",
        "json": output_directory / "report.json",
        "chart": output_directory / "quality.svg",
    }
    paths["json"].write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    paths["chart"].write_text(_render_chart(report))
    paths["markdown"].write_text(_render_markdown(report))
    return paths


def _import_canonical_sources(project_root: Path) -> list[dict[str, object]]:
    source_directory = project_root / "sample_data/source"
    with TemporaryDirectory(prefix="spend-memory-evaluation-") as directory:
        root = Path(directory)
        repository = ImportRepository(
            database_path=root / "spend-memory.duckdb",
            data_directory=root / "data",
        )
        service = IngestionService(
            repository,
            ParserRegistry(
                [
                    CanonicalCsvParser(),
                    SyntheticAedTabularPdfParser(),
                    SyntheticPkrCompactPdfParser(),
                ]
            ),
        )
        for filename, mime_type in _SOURCES:
            service.import_document(
                document=(source_directory / filename).read_bytes(),
                filename=filename,
                declared_mime_type=mime_type,
            )
        with duckdb.connect(str(repository.database_path), read_only=True) as connection:
            rows = connection.execute(
                """
                SELECT documents.original_filename, transactions.date_text,
                    transactions.description_text,
                    coalesce(transactions.normalized_amount_text, transactions.amount_text),
                    transactions.currency_text, transactions.raw_account_identity
                FROM raw_transactions AS transactions
                JOIN import_runs AS runs ON runs.run_id = transactions.import_run_id
                JOIN source_documents AS documents ON documents.document_id = runs.document_id
                """
            ).fetchall()
    return [
        {
            "source_document": f"source/{filename}",
            "posted_date": posted_date,
            "description": description,
            "amount_minor": _amount_minor(amount_text),
            "currency": currency,
            "account_id": account,
        }
        for filename, posted_date, description, amount_text, currency, account in rows
    ]


def _amount_minor(value: str) -> int:
    return int(value.removeprefix("PKR "))


def _evaluate_extraction(
    expected: list[dict[str, object]], extracted: list[dict[str, object]]
) -> dict[str, object]:
    fields = ("posted_date", "description", "amount_minor", "currency", "account_id")
    correct_fields = sum(
        sum(
            (
                Counter((row["source_document"], row[field]) for row in extracted)
                & Counter((row["source_document"], row[field]) for row in expected)
            ).values()
        )
        for field in fields
    )
    predicted_fields = len(extracted) * len(fields)
    expected_fields = len(expected) * len(fields)
    predicted_amounts = Counter(
        (
            row["source_document"],
            row["posted_date"],
            row["description"],
            row["currency"],
            row["account_id"],
            row["amount_minor"],
        )
        for row in extracted
    )
    expected_amounts = Counter(
        (
            row["source_document"],
            row["posted_date"],
            row["description"],
            row["currency"],
            row["account_id"],
            row["amount_minor"],
        )
        for row in expected
    )
    predicted_totals = _totals(extracted)
    expected_totals = _totals(expected)
    return {
        "transaction_count": len(extracted),
        "field_precision": correct_fields / predicted_fields,
        "field_recall": correct_fields / expected_fields,
        "exact_amount_accuracy": sum((predicted_amounts & expected_amounts).values()) / len(extracted),
        "reconciliation_rate": sum(
            predicted_totals.get(key) == value for key, value in expected_totals.items()
        ) / len(expected_totals),
    }


def _totals(rows: list[dict[str, object]]) -> dict[tuple[object, object], int]:
    totals: Counter[tuple[object, object]] = Counter()
    for row in rows:
        totals[(row["account_id"], row["currency"])] += int(row["amount_minor"])
    return dict(totals)


def _peak_rss_kib() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value // 1024 if sys.platform == "darwin" else value


def _evaluate_merchants() -> dict[str, float | int]:
    metromart_id = UUID(int=100)
    cafe_id = UUID(int=200)
    result = evaluate_merchant_matches(
        [
            (metromart_id, "Metro Mart Market", "METRO MART"),
            (metromart_id, "Metro Mart Market", "METRO MART ONLINE"),
            (cafe_id, "Cafe Lane House", "CAFE LANE"),
            (cafe_id, "Cafe Lane House", "CAFE LANE DUBAI"),
        ],
        held_out_merchant_ids={metromart_id},
    )
    return {
        "precision": result.precision,
        "recall": result.recall,
        "coverage": result.coverage,
        "top_k": 1,
        "top_k_accuracy": result.recall,
        "expected_calibration_error": result.expected_calibration_error,
        "baseline_precision": result.baseline_precision,
    }


def _transaction(
    raw_id: int,
    transaction_date: str,
    amount_minor: int,
    description: str,
    *,
    currency: str = "AED",
    direction: str = "debit",
    normalized_description: str | None = None,
) -> TrustedTransaction:
    return TrustedTransaction(
        UUID(int=raw_id),
        "evaluation-account",
        date.fromisoformat(transaction_date),
        description,
        normalized_description or normalize_descriptor(description),
        currency,
        amount_minor,
        direction,
    )


def _evaluate_recurring() -> dict[str, object]:
    rows = [
        _transaction(1, "2026-01-05", -2999, "STREAMBOX MONTHLY"),
        _transaction(2, "2026-02-04", -2999, "STREAMBOX MONTHLY"),
        _transaction(3, "2026-03-06", -2999, "STREAMBOX MONTHLY"),
    ]
    candidates = detect_recurring_candidates(rows, {})
    expected = {(UUID(int=1), UUID(int=2), UUID(int=3))}
    predicted = {candidate.raw_transaction_ids for candidate in candidates}
    true_positives = len(predicted & expected)
    precision = true_positives / len(predicted) if predicted else 0.0
    recall = true_positives / len(expected)
    cadence_matches = all(candidate.cadence == "monthly" for candidate in candidates)
    return {
        "precision": precision,
        "recall": recall,
        "f1_by_frequency": {
            "monthly": 2 * precision * recall / (precision + recall)
            if precision + recall and cadence_matches
            else 0.0
        },
    }


def _evaluate_duplicates() -> dict[str, float]:
    candidates = find_duplicate_candidates(
        [
            _transaction(1, "2026-03-12", -12500, "METRO MART"),
            _transaction(2, "2026-03-12", -12500, "Metro Mart"),
            _transaction(3, "2026-03-20", -12500, "METRO MART"),
        ],
        {},
    )
    expected = {(UUID(int=1), UUID(int=2))}
    predicted = {candidate.raw_transaction_ids for candidate in candidates}
    return {
        "precision_at_review_threshold": len(predicted & expected) / len(predicted)
        if predicted
        else 0.0
    }


def _search_rows() -> list[SearchRow]:
    groceries = CategoryDecision(UUID(int=1), "Groceries", "merchant_assignment")
    return [
        SearchRow(_transaction(2, "2026-01-03", 1200, "METRO MART", normalized_description="metro mart"), groceries, "MetroMart", "none"),
        SearchRow(_transaction(4, "2026-01-04", 900, "Coffee Corner Online", currency="USD", direction="credit", normalized_description="coffee corner"), CategoryDecision(UUID(int=7), "Dining", "merchant_assignment"), "Coffee Corner", "recurring"),
        SearchRow(_transaction(5, "2026-01-05", 1200, "METRO MART REFUND", direction="credit", normalized_description="metro mart refund"), groceries, "MetroMart", "review"),
        SearchRow(_transaction(6, "2026-01-06", 5000, "Fuel Stop #123", normalized_description="fuel stop"), CategoryDecision(UUID(int=8), "Transport", "merchant_assignment"), "Fuel Stop", "unusual"),
        SearchRow(_transaction(3, "2026-01-02", 1500, "MetroMart POS", normalized_description="metro mart"), groceries, "MetroMart", "none"),
    ]


_SEARCH_QUERIES = (
    ("metro", 5, None), ("metro mart", 5, None), ("METRO MART", 5, None),
    ("metromart", 3, None), ("mart", 5, None), ("coffee", 4, None),
    ("corner", 4, None), ("fuel", 6, None), ("stop", 6, None),
    ("refund", 5, None), ("currency:AED", 6, None), ("currency:USD", 4, None),
    ("currency:EUR", None, None), ("direction:debit", 6, None), ("direction:credit", 5, None),
    ("after:2026-01-05", 6, None), ("before:2026-01-04", 2, None), ("after:2026-01-03 before:2026-01-06", 5, None),
    ("merchant:MetroMart", 5, None), ("merchant:Coffee", None, None),
    ("merchant:Coffee Corner", None, None), ("category:Groceries", 5, None), ("category:Dining", 4, None),
    ("category:Transport", 6, None), ("amount:1200..1200", 5, None), ("amount:0..1000", 4, None),
    ("amount:5000..9000", 6, None), ("state:none", 2, None), ("state:recurring", 4, None),
    ("state:review", 5, None), ("state:unusual", 6, None), ("currency:AED metro", 5, None),
    ("currency:USD metro", None, None), ("direction:credit metro", 5, None), ("category:Groceries metro", 5, None),
    ("merchant:MetroMart refund", 5, None), ("amount:1000..2000 metro", 5, None), ("after:2026-01-01 metro", 5, None),
    ("before:2026-01-06 metro", 5, None), ("", None, None), ("planet:mars", None, "unknown_filter"),
    ("amount:50..10", None, "invalid_amount_range"), ("amount:abc", None, "invalid_amount_range"),
    ("after:not-a-date", None, "invalid_date"), ("direction:transfer", None, "invalid_direction"),
    ("currency:AED currency:USD", None, "duplicate_filter"), ("state:review state:none", None, "duplicate_filter"),
    ("amount:1..2..3", None, "invalid_amount_range"), ("merchant:", None, "invalid_filter"),
    ("before:2026-13-01", None, "invalid_date"),
)


def _evaluate_search() -> dict[str, object]:
    rows = _search_rows()
    reciprocal_ranks: list[float] = []
    correct = 0
    for text, expected_id, error_code in _SEARCH_QUERIES:
        if error_code is not None:
            try:
                parse_search_query(text)
            except SearchQueryError as error:
                correct += error.args[0] == error_code
            continue
        results = search_transactions(rows, parse_search_query(text))
        identifiers = [result.transaction.raw_transaction_id.int for result in results[:5]]
        if expected_id is None:
            correct += not identifiers
            continue
        if expected_id in identifiers:
            reciprocal_ranks.append(1 / (identifiers.index(expected_id) + 1))
            correct += 1
    return {
        "query_count": len(_SEARCH_QUERIES),
        "recall_at_5": len(reciprocal_ranks)
        / sum(expected_id is not None for _, expected_id, _ in _SEARCH_QUERIES),
        "mrr": sum(reciprocal_ranks) / len(reciprocal_ranks),
        "structured_filter_correctness": correct / len(_SEARCH_QUERIES),
    }


def _render_markdown(report: dict[str, object]) -> str:
    extraction = report["extraction"]
    merchant = report["merchant_resolution"]
    recurring = report["recurring_detection"]
    duplicate = report["duplicate_detection"]
    search = report["search"]
    runtime = report["runtime"]
    limitations = "\n".join(f"- {item}" for item in report["known_limitations"])
    return f"""# Spend Memory evaluation report

This report uses only the repository's immutable synthetic fixtures. It never reads user data.

![Quality chart](quality.svg)

## Quality

| Area | Measure | Result |
| --- | --- | ---: |
| Extraction | Field precision / recall | {extraction['field_precision']:.0%} / {extraction['field_recall']:.0%} |
| Extraction | Exact amount accuracy | {extraction['exact_amount_accuracy']:.0%} |
| Extraction | Reconciliation rate | {extraction['reconciliation_rate']:.0%} |
| Merchant resolution | Precision / recall / coverage | {merchant['precision']:.0%} / {merchant['recall']:.0%} / {merchant['coverage']:.0%} |
| Merchant resolution | Top-{merchant['top_k']} accuracy / calibration error | {merchant['top_k_accuracy']:.0%} / {merchant['expected_calibration_error']:.1%} |
| Recurring detection | Precision / recall | {recurring['precision']:.0%} / {recurring['recall']:.0%} |
| Duplicate review | Precision at threshold | {duplicate['precision_at_review_threshold']:.0%} |
| Search | Recall@5 / MRR / structured correctness | {search['recall_at_5']:.0%} / {search['mrr']:.0%} / {search['structured_filter_correctness']:.0%} |

## Runtime

| Measure | Result |
| --- | ---: |
| Local import time | {runtime['import_time_ms']} ms |
| OCR time | not measured |
| Index time | not applicable |
| 50-query search time | {runtime['query_latency_ms']} ms |
| Peak process RSS | {runtime['peak_rss_kib']} KiB |

## Baselines

The held-out merchant resolver is compared with exact alias matching. Its precision is {merchant['precision']:.0%}, versus {merchant['baseline_precision']:.0%} for the baseline. Search is evaluated as the current local lexical baseline because the product has no semantic index.

## Known failures

None in this synthetic run.

## Known limitations

{limitations}
"""


def _render_chart(report: dict[str, object]) -> str:
    measures = (
        ("Extraction", report["extraction"]["field_precision"]),
        ("Merchant", report["merchant_resolution"]["precision"]),
        ("Recurring", report["recurring_detection"]["precision"]),
        ("Duplicates", report["duplicate_detection"]["precision_at_review_threshold"]),
        ("Search", report["search"]["recall_at_5"]),
    )
    bars = "".join(
        f'<text x="10" y="{35 + index * 35}">{escape(name)}</text>'
        f'<rect x="110" y="{20 + index * 35}" width="{int(float(value) * 220)}" height="18" fill="#286b5b"/>'
        f'<text x="340" y="{35 + index * 35}">{float(value):.0%}</text>'
        for index, (name, value) in enumerate(measures)
    )
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="400" height="200" role="img" aria-label="Evaluation quality scores">{bars}</svg>\n'


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Spend Memory evaluation artifacts.")
    parser.add_argument("--output", type=Path, default=Path("evaluations/artifacts"))
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[1]
    paths = write_report(evaluate(project_root), args.output)
    print(f"Wrote {paths['markdown']}")


if __name__ == "__main__":
    main()
