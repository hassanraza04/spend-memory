from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

from sample_data.generator.generate import DEFAULT_SEED, generate_dataset


def test_fixed_seed_generates_the_same_canonical_ledger_and_sources(tmp_path) -> None:
    first = generate_dataset(tmp_path / "first", seed=DEFAULT_SEED)
    second = generate_dataset(tmp_path / "second", seed=DEFAULT_SEED)

    assert first.ledger == second.ledger
    assert first.ledger["metadata"]["transaction_count"] >= 800
    assert first.ledger["metadata"]["month_count"] >= 25
    assert sha256(first.csv_path.read_bytes()).hexdigest() == sha256(
        second.csv_path.read_bytes()
    ).hexdigest()
    for filename in ("aed_statement_tabular.pdf", "pkr_statement_compact.pdf"):
        assert sha256((first.csv_path.parent / filename).read_bytes()).hexdigest() == sha256(
            (second.csv_path.parent / filename).read_bytes()
        ).hexdigest()


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

    assert len(list(tmp_path.glob("source/*.pdf"))) == 2
    assert len(list(tmp_path.glob("source/*.csv"))) == 1
