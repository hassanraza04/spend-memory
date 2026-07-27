"""Generate deterministic synthetic statements and their canonical ledger."""

from __future__ import annotations

import csv
import json
import random
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas

DEFAULT_SEED = 20260727
AED_ACCOUNT = "AED-SYNTH-001"
PKR_ACCOUNT = "PKR-SYNTH-001"
CSV_COLUMNS = (
    "transaction_id",
    "posted_date",
    "account_id",
    "currency",
    "amount_minor",
    "description",
    "transaction_type",
)


@dataclass(frozen=True)
class GeneratedDataset:
    ledger: dict[str, Any]
    reconciliation: dict[str, Any]
    csv_path: Path


def _months() -> list[date]:
    return [date(2024 + (month - 1) // 12, (month - 1) % 12 + 1, 1) for month in range(1, 26)]


def _add_transaction(
    transactions: list[dict[str, Any]],
    *,
    posted_date: date,
    account_id: str,
    currency: str,
    amount_minor: int,
    description: str,
    transaction_type: str,
    edge_case: str | None = None,
) -> None:
    transaction_id = f"SYN-{len(transactions) + 1:05d}"
    transactions.append(
        {
            "transaction_id": transaction_id,
            "posted_date": posted_date.isoformat(),
            "account_id": account_id,
            "currency": currency,
            "amount_minor": amount_minor,
            "description": description,
            "transaction_type": transaction_type,
            "edge_case": edge_case,
        }
    )


def _make_transactions(seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    transactions: list[dict[str, Any]] = []
    merchants = (
        ("MetroMart", ("METRO MART", "MetroMart POS", "METRO-MART")),
        ("BrewLab", ("BREWLAB", "Brew Lab Cafe", "BREW-LAB")),
        ("QuickCart", ("QUICKCART APP", "Quick Cart", "QKCRT*ONLINE")),
        ("Orbit Fuel", ("ORBIT FUEL", "OrbitFuel Station", "ORBIT-FUEL")),
        ("Pixel Books", ("PIXEL BOOKS", "PixelBooks Online", "PXLBKS")),
        ("Harbor Pharmacy", ("HARBOR PHARMACY", "Harbor Pharm", "HBR PHARM")),
    )
    for month_start in _months():
        for account_id, currency, low, high in (
            (AED_ACCOUNT, "AED", 275, 18450),
            (PKR_ACCOUNT, "PKR", 8500, 345000),
        ):
            for _ in range(16):
                _, descriptions = rng.choice(merchants)
                _add_transaction(
                    transactions,
                    posted_date=month_start + timedelta(days=rng.randrange(0, 27)),
                    account_id=account_id,
                    currency=currency,
                    amount_minor=-rng.randrange(low, high),
                    description=rng.choice(descriptions),
                    transaction_type="debit",
                )
            _add_transaction(
                transactions,
                posted_date=month_start + timedelta(days=2),
                account_id=account_id,
                currency=currency,
                amount_minor=-2999 if currency == "AED" else -110000,
                description="STREAMBOX MONTHLY" if currency == "AED" else "CLOUDNOTE MONTHLY",
                transaction_type="debit",
                edge_case="monthly_recurring",
            )
            if month_start.month == 1:
                _add_transaction(
                    transactions,
                    posted_date=month_start + timedelta(days=5),
                    account_id=account_id,
                    currency=currency,
                    amount_minor=-12999 if currency == "AED" else -480000,
                    description="ATLAS COVER ANNUAL" if currency == "AED" else "ATLAS COVER YEARLY",
                    transaction_type="debit",
                    edge_case="annual_recurring",
                )

    _add_transaction(transactions, posted_date=date(2024, 3, 12), account_id=AED_ACCOUNT, currency="AED", amount_minor=-12500, description="METRO MART", transaction_type="debit", edge_case="same_day_equal_value")
    _add_transaction(transactions, posted_date=date(2024, 3, 12), account_id=AED_ACCOUNT, currency="AED", amount_minor=-12500, description="MetroMart POS", transaction_type="debit", edge_case="same_day_equal_value")
    _add_transaction(transactions, posted_date=date(2024, 9, 8), account_id=PKR_ACCOUNT, currency="PKR", amount_minor=-225000, description="QUICKCART APP", transaction_type="debit", edge_case="true_duplicate")
    _add_transaction(transactions, posted_date=date(2024, 9, 8), account_id=PKR_ACCOUNT, currency="PKR", amount_minor=-225000, description="QUICKCART APP", transaction_type="debit", edge_case="true_duplicate")
    _add_transaction(transactions, posted_date=date(2025, 2, 19), account_id=AED_ACCOUNT, currency="AED", amount_minor=8600, description="PIXEL BOOKS REFUND", transaction_type="credit", edge_case="refund")
    _add_transaction(transactions, posted_date=date(2025, 5, 4), account_id=PKR_ACCOUNT, currency="PKR", amount_minor=178500, description="ORBIT FUEL REVERSAL", transaction_type="credit", edge_case="reversal")
    _add_transaction(transactions, posted_date=date(2025, 10, 22), account_id=AED_ACCOUNT, currency="AED", amount_minor=-985000, description="NOVA WORKSTATION FIRST ORDER", transaction_type="debit", edge_case="first_time_large_purchase")
    _add_transaction(transactions, posted_date=date(2025, 11, 18), account_id=PKR_ACCOUNT, currency="PKR", amount_minor=-32500000, description="NOVA WORKSTATION FIRST ORDER", transaction_type="debit", edge_case="first_time_large_purchase")
    return sorted(transactions, key=lambda item: (item["posted_date"], item["transaction_id"]))


def _source_for(transaction: dict[str, Any]) -> str:
    if transaction["account_id"] == PKR_ACCOUNT:
        return "source/pkr_statement_compact.pdf"
    if transaction["posted_date"] >= "2026-01-01":
        return "source/aed_january_2026.csv"
    return "source/aed_statement_tabular.pdf"


def _write_csv(path: Path, transactions: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for transaction in transactions:
            writer.writerow({column: transaction[column] for column in CSV_COLUMNS})


def _write_aed_pdf(path: Path, transactions: list[dict[str, Any]]) -> None:
    canvas = Canvas(str(path), pagesize=A4, invariant=1)
    _, height = A4
    y = height - 20 * mm
    canvas.setFont("Helvetica-Bold", 16)
    canvas.drawString(18 * mm, y, "SYNTHETIC AED STATEMENT | TABULAR LAYOUT")
    y -= 10 * mm
    canvas.setFont("Helvetica-Bold", 8)
    canvas.drawString(18 * mm, y, "Date")
    canvas.drawString(48 * mm, y, "Description")
    canvas.drawRightString(180 * mm, y, "Amount (fils)")
    for transaction in transactions:
        y -= 5 * mm
        if y < 18 * mm:
            canvas.showPage()
            y = height - 20 * mm
            canvas.setFont("Helvetica-Bold", 8)
            canvas.drawString(18 * mm, y, "Date")
            canvas.drawString(48 * mm, y, "Description")
            canvas.drawRightString(180 * mm, y, "Amount (fils)")
        canvas.setFont("Helvetica", 8)
        canvas.drawString(18 * mm, y, transaction["posted_date"])
        canvas.drawString(48 * mm, y, transaction["description"][:42])
        canvas.drawRightString(180 * mm, y, str(transaction["amount_minor"]))
    canvas.save()


def _write_pkr_pdf(path: Path, transactions: list[dict[str, Any]]) -> None:
    canvas = Canvas(str(path), pagesize=letter, invariant=1)
    width, height = letter
    y = height - 60
    canvas.setFillColorRGB(0, 0.18, 0.34)
    canvas.rect(0, height - 58, width, 58, fill=1, stroke=0)
    canvas.setFillColorRGB(1, 1, 1)
    canvas.setFont("Helvetica-Bold", 15)
    canvas.drawString(36, height - 35, "SYNTHETIC PKR ACTIVITY")
    canvas.setFillColorRGB(0, 0, 0)
    for transaction in transactions:
        y -= 18
        if y < 36:
            canvas.showPage()
            y = height - 78
            canvas.setFillColorRGB(0, 0.18, 0.34)
            canvas.rect(0, height - 58, width, 58, fill=1, stroke=0)
            canvas.setFillColorRGB(1, 1, 1)
            canvas.setFont("Helvetica-Bold", 15)
            canvas.drawString(36, height - 35, "SYNTHETIC PKR ACTIVITY")
            canvas.setFillColorRGB(0, 0, 0)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawString(36, y, transaction["description"][:55])
        canvas.setFont("Helvetica", 8)
        canvas.drawString(36, y - 9, transaction["posted_date"])
        canvas.drawRightString(width - 36, y, f"PKR {transaction['amount_minor']}")
    canvas.save()


def _reconcile(transactions: list[dict[str, Any]]) -> dict[str, Any]:
    totals: dict[str, int] = {}
    for transaction in transactions:
        key = f"{transaction['account_id']}:{transaction['currency']}"
        totals[key] = totals.get(key, 0) + transaction["amount_minor"]
    return {"is_reconciled": True, "by_account_currency": totals}


def generate_dataset(output_directory: Path, *, seed: int = DEFAULT_SEED) -> GeneratedDataset:
    """Write all fixtures under output_directory and return their canonical ledger."""
    source_directory = output_directory / "source"
    expected_directory = output_directory / "expected"
    source_directory.mkdir(parents=True, exist_ok=True)
    expected_directory.mkdir(parents=True, exist_ok=True)
    transactions = _make_transactions(seed)
    for transaction in transactions:
        transaction["source_document"] = _source_for(transaction)
    reconciliation = _reconcile(transactions)
    ledger = {
        "metadata": {
            "seed": seed,
            "transaction_count": len(transactions),
            "month_count": len(_months()),
            "date_range": {"start": transactions[0]["posted_date"], "end": transactions[-1]["posted_date"]},
            "amount_representation": "signed integer minor units; no floating-point values",
        },
        "transactions": transactions,
        "reconciliation": reconciliation,
    }
    csv_transactions = [item for item in transactions if item["source_document"].endswith(".csv")]
    aed_transactions = [item for item in transactions if item["source_document"].endswith("tabular.pdf")]
    pkr_transactions = [item for item in transactions if item["source_document"].endswith("compact.pdf")]
    csv_path = source_directory / "aed_january_2026.csv"
    _write_csv(csv_path, csv_transactions)
    _write_aed_pdf(source_directory / "aed_statement_tabular.pdf", aed_transactions)
    _write_pkr_pdf(source_directory / "pkr_statement_compact.pdf", pkr_transactions)
    (expected_directory / "canonical_ledger.json").write_text(
        json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (expected_directory / "reconciliation.json").write_text(
        json.dumps(reconciliation, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return GeneratedDataset(ledger=ledger, reconciliation=reconciliation, csv_path=csv_path)


if __name__ == "__main__":
    generate_dataset(Path(__file__).resolve().parents[1])
