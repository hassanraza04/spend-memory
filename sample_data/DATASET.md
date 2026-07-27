# Synthetic Spend-Memory Dataset

This directory contains deterministic, invented financial fixtures for future ingestion tests. It contains no real names, account numbers, addresses, merchants, or financial activity.

## Generate

```sh
uv run python -m sample_data.generator.generate
```

The fixed seed is `20260727`. The generated ledger covers 25 calendar months, from 2024-01-01 through 2026-01-27. All monetary amounts are signed integer minor units. Negative values are debits and positive values are credits. No value, balance, total, or reconciliation calculation uses a floating-point number.

## Source documents

- `source/aed_statement_tabular.pdf`: AED account `AED-SYNTH-001`, tabular A4 layout, January 2024 through December 2025.
- `source/pkr_statement_compact.pdf`: PKR account `PKR-SYNTH-001`, compact letter layout with a blue header and two-line activity rows, January 2024 through January 2026.
- `source/aed_january_2026.csv`: AED account `AED-SYNTH-001`, January 2026 only.

The documents partition the canonical ledger. They are not alternative copies of the same transactions. AED and PKR never share an account identifier or currency.

## Canonical CSV format

The CSV is UTF-8, comma-delimited, includes a header row, uses `\n` line endings, and has exactly these columns in this order:

| Column | Format | Meaning |
| --- | --- | --- |
| `transaction_id` | `SYN-` plus five digits | Stable synthetic record ID. |
| `posted_date` | ISO 8601 `YYYY-MM-DD` | Posted transaction date. |
| `account_id` | String | Synthetic account ID. |
| `currency` | ISO 4217 code | `AED` or `PKR`. |
| `amount_minor` | Signed base-10 integer | Debit is negative, credit is positive. AED uses fils and PKR uses paisa. |
| `description` | UTF-8 text | Raw, intentionally inconsistent merchant description. |
| `transaction_type` | `debit` or `credit` | Source transaction direction. |

`expected/canonical_ledger.json` is the source of truth for later parser tests. It adds `edge_case` and `source_document` to every canonical transaction. `expected/reconciliation.json` records signed totals by account and currency.

## Deliberate edge cases

The ledger includes inconsistent merchant descriptions, monthly and annual recurring payments, a refund, a reversal, same-day equal-value legitimate purchases, exactly one duplicate-charge pair, and first-time unusually large purchases. The fixtures are for extraction and reconciliation evaluation only. They do not model a complete bank statement specification, real exchange rates, balances, fees, or tax treatment.
