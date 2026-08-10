from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from evaluations.generate import _peak_rss_kib, evaluate, write_report

PROJECT_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def report() -> dict[str, object]:
    return evaluate(PROJECT_ROOT)


def test_evaluation_uses_immutable_synthetic_ground_truth(report: dict[str, object]) -> None:

    assert report["extraction"] == {
        "transaction_count": 864,
        "field_precision": 1.0,
        "field_recall": 1.0,
        "exact_amount_accuracy": 1.0,
        "reconciliation_rate": 1.0,
    }
    assert report["merchant_resolution"]["precision"] == 1.0
    assert report["merchant_resolution"]["top_k"] == 1
    assert report["merchant_resolution"]["baseline_precision"] == 0.0
    assert report["recurring_detection"] == {
        "precision": 1.0,
        "recall": 1.0,
        "f1_by_frequency": {"monthly": 1.0},
    }
    assert report["duplicate_detection"]["precision_at_review_threshold"] == 1.0
    assert report["search"] == {
        "query_count": 50,
        "recall_at_5": 1.0,
        "mrr": 1.0,
        "structured_filter_correctness": 1.0,
    }
    assert report["deferred_metrics"] == {
        "category_learning": "not implemented",
        "semantic_index": "not implemented",
        "ocr": "excluded from the canonical ledger",
    }
    assert report["runtime"]["index_time_ms"] is None
    assert report["runtime"]["import_time_ms"] >= 0
    assert report["runtime"]["query_latency_ms"] >= 0
    assert report["runtime"]["peak_rss_kib"] > 0


def test_evaluation_writes_markdown_json_and_chart_artifacts(
    report: dict[str, object], tmp_path: Path
) -> None:
    paths = write_report(report, tmp_path)

    markdown = paths["markdown"].read_text()
    payload = json.loads(paths["json"].read_text())
    chart = paths["chart"].read_text()

    assert "# Spend Memory evaluation report" in markdown
    assert "Known failures" in markdown
    assert "Known limitations" in markdown
    assert payload["extraction"]["transaction_count"] == 864
    assert "<svg" in chart


@patch("evaluations.generate.resource.getrusage")
@patch("evaluations.generate.sys.platform", "darwin")
def test_peak_rss_converts_macos_bytes_to_kib(getrusage) -> None:
    getrusage.return_value = SimpleNamespace(ru_maxrss=10_240)

    assert _peak_rss_kib() == 10
