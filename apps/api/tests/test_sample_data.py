from __future__ import annotations

from hashlib import sha256

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


def test_reconciliation_matches_each_currency_account_and_exposes_required_edges(tmp_path) -> None:
    dataset = generate_dataset(tmp_path, seed=DEFAULT_SEED)
    transactions = dataset.ledger["transactions"]

    assert {item["account_id"] for item in transactions} == {
        "AED-SYNTH-001",
        "PKR-SYNTH-001",
    }
    assert {item["currency"] for item in transactions} == {"AED", "PKR"}
    assert all(isinstance(item["amount_minor"], int) for item in transactions)
    assert all("float" not in repr(item["amount_minor"]).lower() for item in transactions)
    assert dataset.reconciliation["is_reconciled"] is True
    assert dataset.reconciliation["by_account_currency"]

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
