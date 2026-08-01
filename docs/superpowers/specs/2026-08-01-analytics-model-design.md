# Milestone 3 analytics model design

## Purpose and scope

Milestone 3 turns active, source-faithful imported rows into deterministic
analytics tables. It covers Tasks 7 through 9 only: staging, reconciliation,
and user-facing marts. Merchant resolution, categories, recurring groups, and
search remain Milestone 4 work.

The implementation uses dbt-core with dbt-duckdb. DuckDB remains local. dbt
reads the existing `main` schema and writes only models and seeds in an
`analytics` schema in the same local database file. It never opens source
documents or changes ingestion tables.

## Data boundary

`source_documents`, `import_runs`, and `raw_transactions` are dbt sources.
Only rows from `import_runs.is_active = true` can reach staging. This preserves
ADR 0003: a newer parser run replaces an older active run for analytics without
deleting the older run or its lineage.

Staging retains `raw_transaction_id`, `import_run_id`, `document_id`, source
page, source row, source ordinal, extraction method, confidence, parser ID,
and parser version. Every intermediate model and mart keeps the source IDs it
needs to trace a value back to an imported row.

Raw fields are never overwritten. Staging uses `normalized_amount_text` only as
an explicit OCR correction and keeps `amount_text` alongside it.

## Model layers

### Staging

One model handles each supported parser family:

- `stg_canonical_csv_transactions`
- `stg_synthetic_aed_pdf_transactions`
- `stg_synthetic_pkr_pdf_transactions`
- `stg_transactions`, the union with a common canonical contract
- `stg_transaction_rejections`, the quarantine table for invalid rows

Each family model parses only its documented format. It validates a date,
currency, integer minor-unit amount, direction, non-empty description, and
source identity. It emits a valid row or a rejection row with an explicit
reason. It does not guess ambiguous values.

Canonical amount fields follow ADR 0001: `amount_minor` is non-negative and
`direction` is `debit` or `credit`. A signed `net_amount_minor` is derived only
for aggregation: debit is negative and credit is positive. No model uses a
floating-point monetary value.

dbt source freshness is configured for imported documents. dbt schema tests
cover unique active raw IDs, non-null descriptions, accepted currencies, valid
directions, and accepted parser IDs.

### Intermediate reconciliation

`int_duplicate_candidates` records reviewable candidate pairs and scores. It
does not delete, merge, or mark either transaction as a duplicate.

`int_running_balance_checks` compares an available parsed running balance with
the previous balance and signed amount, partitioned by import run and account.
It records `not_available`, `pass`, or `fail`; it does not invent missing
balances.

`int_import_reconciliation` assigns every active import one explicit status:

- `reconciled` when an imported synthetic statement matches its deterministic
  source control total and any available running-balance checks pass.
- `unreconciled` when an available control total or running balance disagrees.
- `not_available` when the parser provides no control total or usable balance.

The synthetic control totals are a generated dbt seed derived from the
committed canonical ledger, keyed by original filename, account, and currency.
The generator remains the single source of synthetic truth. Real imports are
never labelled reconciled merely because they lack a control total.

Trusted marts include only `reconciled` imports by default. A separate explicit
diagnostic model exposes `not_available` imports for future review flows. This
keeps an unreconciled import out of default aggregates without deleting it.

### Marts

The stable contracts are:

- `mart_transactions`
- `mart_merchants`
- `mart_categories`
- `mart_recurring_groups`
- `mart_monthly_summary`
- `mart_category_summary`
- `mart_period_comparisons`

`mart_transactions` uses the raw transaction ID as its stable transaction ID
until Milestone 4 adds enrichment. Merchant, category, and recurring fields
are nullable and state their unavailable enrichment version rather than using
guessed values. The related dimensions exist with their future contract shape
but contain no invented classifications.

Monthly and category summaries group by account and currency. They never mix
AED and PKR. Period comparisons are also account-and-currency scoped and use
integer SQL sums. Their contribution rows include the before amount, after
amount, and exact difference. Contributions must sum exactly to the observed
period difference for every comparison key.

## Configuration and execution

The repository contains an `analytics` dbt project and a repository-local
profile template. The database location comes from `SPEND_MEMORY_DUCKDB_PATH`.
Local commands can target a copied or synthetic DuckDB file; no user data is
committed, uploaded, or used by CI.

dbt-core and dbt-duckdb are development dependencies. Docker and the FastAPI
runtime do not need dbt until a later milestone wires an explicit local
analytics command into the application.

## Tests and checks

The Milestone 3 test suite will build a temporary DuckDB fixture from synthetic
imports and run `dbt build`. It verifies:

- source freshness configuration and source schema contracts;
- staging acceptance and explicit rejection reasons;
- active-run filtering and parser-version reprocessing;
- source-total and running-balance reconciliation states;
- no deletion by duplicate-candidate logic;
- lineage columns on every mart;
- exact monthly, category, and period-comparison totals against the committed
  synthetic ledger; and
- exclusion of `unreconciled` and `not_available` imports from trusted marts.

## Non-goals

This milestone adds no ML, embeddings, categories, merchant matching, recurring
detection, API routes, UI screens, cloud service, or real-bank adapter. It also
does not alter the source document, raw transaction, or import-run contracts.
