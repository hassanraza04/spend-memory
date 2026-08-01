from __future__ import annotations

import csv
import json
import tomllib
from hashlib import sha256
from pathlib import Path

import fitz

from sample_data.generator.generate import DEFAULT_SEED, generate_dataset

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_reportlab_is_a_development_only_dependency() -> None:
    configuration = tomllib.loads(
        (REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )

    assert not any(
        dependency.startswith("reportlab")
        for dependency in configuration["project"]["dependencies"]
    )
    assert any(
        dependency.startswith("reportlab")
        for dependency in configuration["dependency-groups"]["dev"]
    )


def test_fixed_seed_regeneration_matches_committed_dataset_artifacts(tmp_path) -> None:
    generate_dataset(tmp_path, seed=DEFAULT_SEED)

    for generated_path, committed_path in (
        (tmp_path / "expected/canonical_ledger.json", "sample_data/expected/canonical_ledger.json"),
        (tmp_path / "expected/reconciliation.json", "sample_data/expected/reconciliation.json"),
        (tmp_path / "source/aed_january_2026.csv", "sample_data/source/aed_january_2026.csv"),
        (tmp_path / "source/aed_statement_tabular.pdf", "sample_data/source/aed_statement_tabular.pdf"),
        (
            tmp_path / "source/aed_statement_image_only.pdf",
            "sample_data/source/aed_statement_image_only.pdf",
        ),
        (tmp_path / "source/pkr_statement_compact.pdf", "sample_data/source/pkr_statement_compact.pdf"),
    ):
        assert generated_path.read_bytes() == (REPOSITORY_ROOT / committed_path).read_bytes()


def test_pkr_first_activity_row_on_every_page_starts_below_header_banner(tmp_path) -> None:
    generate_dataset(tmp_path, seed=DEFAULT_SEED)

    with fitz.open(tmp_path / "source/pkr_statement_compact.pdf") as document:
        for page in document:
            activity_spans = [
                span
                for block in page.get_text("dict")["blocks"]
                for line in block.get("lines", [])
                for span in line["spans"]
                if span["text"] != "SYNTHETIC PKR ACTIVITY"
            ]
            assert min(span["bbox"][1] for span in activity_spans) >= 58


def test_docker_context_excludes_sensitive_and_bulky_local_paths() -> None:
    ignored_paths = {
        line.strip()
        for line in (REPOSITORY_ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }

    assert {
        ".env",
        ".git/",
        ".venv/",
        "node_modules/",
        ".pytest_cache/",
        "apps/api/data/",
        ".superpowers/",
    } <= ignored_paths
    assert "sample_data/" not in ignored_paths


def test_make_lint_checks_api_and_sample_data() -> None:
    makefile = (REPOSITORY_ROOT / "Makefile").read_text(encoding="utf-8")

    assert "uv run ruff check apps/api sample_data" in makefile


def test_fixed_seed_generates_the_same_canonical_ledger_and_sources(tmp_path) -> None:
    first = generate_dataset(tmp_path / "first", seed=DEFAULT_SEED)
    second = generate_dataset(tmp_path / "second", seed=DEFAULT_SEED)

    assert first.ledger == second.ledger
    assert first.ledger["metadata"]["transaction_count"] >= 800
    assert first.ledger["metadata"]["month_count"] >= 25
    assert sha256(first.csv_path.read_bytes()).hexdigest() == sha256(
        second.csv_path.read_bytes()
    ).hexdigest()
    for filename in (
        "aed_statement_image_only.pdf",
        "aed_statement_tabular.pdf",
        "pkr_statement_compact.pdf",
    ):
        assert sha256((first.csv_path.parent / filename).read_bytes()).hexdigest() == sha256(
            (second.csv_path.parent / filename).read_bytes()
        ).hexdigest()


def test_import_controls_are_deterministic_and_match_ledger(tmp_path) -> None:
    first = generate_dataset(tmp_path / "first", seed=DEFAULT_SEED)
    generate_dataset(tmp_path / "second", seed=DEFAULT_SEED)
    first_controls = (tmp_path / "first/expected/import_controls.csv").read_bytes()
    second_controls = (tmp_path / "second/expected/import_controls.csv").read_bytes()

    assert first_controls == second_controls

    controls = list(csv.DictReader(first_controls.decode("utf-8").splitlines()))
    control_totals = {
        (row["original_filename"], row["account_identity"], row["currency"]): int(
            row["expected_net_amount_minor"]
        )
        for row in controls
    }
    ledger_totals: dict[tuple[str, str, str], int] = {}
    for transaction in first.ledger["transactions"]:
        key = (
            Path(transaction["source_document"]).name,
            transaction["account_id"],
            transaction["currency"],
        )
        ledger_totals[key] = ledger_totals.get(key, 0) + transaction["amount_minor"]

    assert control_totals == ledger_totals


def test_reconciliation_matches_each_currency_account_and_exposes_required_edges(tmp_path) -> None:
    dataset = generate_dataset(tmp_path, seed=DEFAULT_SEED)
    transactions = dataset.ledger["transactions"]
    expected_reconciliation = json.loads(
        (
            Path(__file__).resolve().parents[3]
            / "sample_data/expected/reconciliation.json"
        ).read_text(encoding="utf-8")
    )
    generated_reconciliation = json.loads(
        (tmp_path / "expected/reconciliation.json").read_text(encoding="utf-8")
    )

    assert {item["account_id"] for item in transactions} == {
        "AED-SYNTH-001",
        "PKR-SYNTH-001",
    }
    assert {item["currency"] for item in transactions} == {"AED", "PKR"}
    assert all(isinstance(item["amount_minor"], int) for item in transactions)
    assert all("float" not in repr(item["amount_minor"]).lower() for item in transactions)
    assert dataset.reconciliation == expected_reconciliation
    assert generated_reconciliation == expected_reconciliation
    assert dataset.ledger["reconciliation"] == expected_reconciliation
    assert expected_reconciliation["by_account_currency"] == {
        "AED-SYNTH-001:AED": -4827840,
        "PKR-SYNTH-001:PKR": -109527423,
    }

    edge_cases = {item["edge_case"] for item in transactions if item["edge_case"]}
    assert {
        "monthly_recurring",
        "annual_recurring",
        "refund",
        "reversal",
        "same_day_equal_value",
        "true_duplicate",
        "first_time_large_purchase",
    } <= edge_cases

    assert len(list(tmp_path.glob("source/*.pdf"))) == 3
    assert len(list(tmp_path.glob("source/*.csv"))) == 1
