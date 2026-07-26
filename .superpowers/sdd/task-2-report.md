# Task 2 Report: Synthetic Financial Data

## Outcome

- Status: complete locally, pending push confirmation.
- Seed: `20260727`.
- Transaction count: `864`.
- Date range: `2024-01-01` through `2026-01-27` across 25 calendar months.
- Currency and account separation: AED uses `AED-SYNTH-001` only; PKR uses `PKR-SYNTH-001` only. No transaction mixes account or currency.
- Amounts: signed integer minor units only. AED values are fils and PKR values are paisa. No floating-point values are generated, stored, or reconciled.

## Fixtures

- `sample_data/source/aed_statement_tabular.pdf`: synthetic AED tabular A4 statement layout.
- `sample_data/source/pkr_statement_compact.pdf`: synthetic PKR compact letter statement layout with a visually distinct header and row treatment.
- `sample_data/source/aed_january_2026.csv`: the one canonical CSV source document.
- `sample_data/expected/canonical_ledger.json`: canonical expected ledger for all source documents.
- `sample_data/expected/reconciliation.json`: expected totals by account and currency.

The source files partition the ledger: AED PDF covers January 2024 through December 2025, AED CSV covers January 2026, and PKR PDF covers the full range. The dataset contains invented identifiers and merchant names only, with no personal or financial data.

## Reconciliation output

```json
{"by_account_currency": {"AED-SYNTH-001:AED": -4827840, "PKR-SYNTH-001:PKR": -109527423}, "is_reconciled": true}
```

## TDD evidence

Red command:

```text
UV_CACHE_DIR=.uv-cache uv run pytest apps/api/tests/test_sample_data.py
ModuleNotFoundError: No module named 'sample_data'
```

Green command:

```text
UV_CACHE_DIR=.uv-cache uv run pytest apps/api/tests/test_sample_data.py
2 passed in 1.97s
```

The deterministic test compares the canonical ledger and CSV bytes from two fixed-seed generation runs. The reconciliation test checks transaction count, month count, account and currency separation, integer amounts, all required edge labels, both PDFs, the CSV, and the per-account reconciliation result.

## Validation and delivery

Task-relevant tests, project tests, and lint are recorded after final validation below. ReportLab `4.5.1` was added and locked in `uv.lock` for deterministic PDF fixture generation. Commit and push status are recorded after delivery.

## Concerns

- PDFs deliberately use two controlled synthetic layouts. They are fixtures, not attempts to emulate a specific real institution.
- PDF byte-for-byte determinism is not asserted across ReportLab versions. The dependency is locked, and the generator uses ReportLab invariant mode to stabilize output within the locked environment.
