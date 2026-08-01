# Analytics Models Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build deterministic, local dbt models that turn active imported statement rows into reconciled and traceable analytics tables.

**Architecture:** A repository-local dbt project reads the existing DuckDB `main` schema through declared sources and writes only to an `analytics` schema in that same file. Staging preserves raw lineage while making amounts and directions canonical. Intermediate models expose rejection, duplicate, balance, and reconciliation evidence; marts consume only imports whose reconciliation status is `reconciled`.

**Tech Stack:** Python 3.12, DuckDB, dbt-core, dbt-duckdb, pytest, uv, SQL, existing synthetic data generator.

## Global Constraints

- Add `dbt-core>=1.9,<2.0` and `dbt-duckdb>=1.9,<2.0` only to the Python development dependency group.
- Read the database file only from `SPEND_MEMORY_DUCKDB_PATH`; default no model to a user-data path.
- dbt sources are `main.source_documents`, `main.import_runs`, and `main.raw_transactions`; dbt writes only into `analytics`.
- Model only `import_runs.is_active = true`. Never mutate imported tables or source files.
- Keep raw `amount_text` and `normalized_amount_text`; use the normalized value only as an explicit correction.
- Represent canonical money as a non-negative integer `amount_minor` plus `debit` or `credit`. Derive signed `net_amount_minor` only in SQL aggregation.
- Keep AED and PKR separate in every aggregate and comparison. Never use floating-point monetary values.
- A staging row is valid or appears in `stg_transaction_rejections` with one explicit reason. Do not guess ambiguous values.
- Only `reconciled` imports enter trusted marts. Preserve duplicate candidates and all rejected or unreconciled evidence.
- Do not add ML, embeddings, merchant matching, category inference, recurring detection, API routes, UI, authentication, hosted storage, or financial integrations.
- Use test-first changes, Ponytail's smallest useful solution, short natural commits, and push each commit to `origin` on `feature/analytics-models`.

---

## File Structure

- `analytics/dbt_project.yml`: dbt project name, model paths, seed paths, and `analytics` schema settings.
- `analytics/profiles.yml`: local DuckDB profile using `SPEND_MEMORY_DUCKDB_PATH`.
- `analytics/models/sources.yml`: source declarations, source freshness, and source contracts.
- `analytics/macros/active_raw_transactions.sql`: one reusable active-import relation with document and parser lineage.
- `analytics/macros/money.sql`: one reusable, integer-only amount parser and signed amount expression.
- `analytics/models/staging/*.sql` and `staging.yml`: parser-family models, a typed union, and a rejection quarantine relation.
- `analytics/seeds/import_controls.csv`: generated synthetic source-control totals, never hand-maintained.
- `analytics/models/intermediate/*.sql` and `intermediate.yml`: duplicate candidates, running balance checks, control reconciliation, and import status.
- `analytics/models/marts/*.sql` and `marts.yml`: trusted transaction-level and aggregate contracts.
- `analytics/tests/*.sql`: assertions which span a result set and cannot be stated as per-column schema tests.
- `apps/api/tests/test_analytics_models.py`: fixture database builder, dbt invocation, and end-to-end contract checks.
- `sample_data/generator/generate.py`: writes control seed from the canonical ledger with the same deterministic generator.
- `pyproject.toml`, `uv.lock`, `Makefile`, and `README.md`: dependency lock and documented local analytics commands.

## Task 1: Add the local dbt project and staging contract

**Files:**
- Create: `analytics/dbt_project.yml`
- Create: `analytics/profiles.yml`
- Create: `analytics/models/sources.yml`
- Create: `analytics/macros/active_raw_transactions.sql`
- Create: `analytics/macros/money.sql`
- Create: `analytics/models/staging/stg_canonical_csv_transactions.sql`
- Create: `analytics/models/staging/stg_synthetic_aed_pdf_transactions.sql`
- Create: `analytics/models/staging/stg_synthetic_pkr_pdf_transactions.sql`
- Create: `analytics/models/staging/stg_transactions.sql`
- Create: `analytics/models/staging/stg_transaction_rejections.sql`
- Create: `analytics/models/staging/staging.yml`
- Create: `apps/api/tests/test_analytics_models.py`
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `Makefile`
- Modify: `README.md`

**Interfaces:**
- Consumes: the `main` tables in migration `0001_import_storage.sql` and parser IDs `canonical-csv`, `synthetic-aed-tabular-pdf`, and `synthetic-pkr-compact-pdf`.
- Produces: `analytics.stg_transactions` with `raw_transaction_id`, `import_run_id`, `document_id`, `original_filename`, `parser_id`, `parser_version`, `transaction_date`, `description`, `amount_text`, `normalized_amount_text`, `currency`, `amount_minor`, `direction`, `net_amount_minor`, `account_identity`, source coordinates, extraction metadata, and `is_valid`; and `analytics.stg_transaction_rejections` with the same lineage plus `rejection_reason`.

- [ ] **Step 1: Write the failing staging integration test**

Add this test scaffold to `apps/api/tests/test_analytics_models.py`. Its helper intentionally uses the production import service so the dbt fixture has the same persisted data as a local import.

```python
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import duckdb
import pytest

from sample_data.generator.generate import generate_dataset
from spend_memory.ingestion.service import IngestionService
from spend_memory.storage.repository import ImportRepository


def _build_fixture_database(tmp_path: Path) -> Path:
    dataset = generate_dataset(tmp_path / "sample_data")
    database_path = tmp_path / "spend-memory.duckdb"
    repository = ImportRepository(database_path, tmp_path / "documents")
    service = IngestionService(repository)
    for source_path in sorted((dataset.csv_path.parent).glob("*.pdf")):
        if source_path.name != "aed_statement_image_only.pdf":
            service.import_document(source_path.read_bytes(), source_path.name, "application/pdf")
    service.import_document(dataset.csv_path.read_bytes(), dataset.csv_path.name, "text/csv")
    return database_path


def _dbt_build(database_path: Path, select: str | None = None) -> None:
    environment = {**os.environ, "SPEND_MEMORY_DUCKDB_PATH": str(database_path)}
    command = ["uv", "run", "dbt", "build", "--project-dir", "analytics", "--profiles-dir", "analytics"]
    if select:
        command.extend(["--select", select])
    subprocess.run(command, check=True, env=environment, text=True)


def test_dbt_builds_staging_models_from_active_imports(tmp_path: Path) -> None:
    database_path = _build_fixture_database(tmp_path)
    _dbt_build(database_path, "stg_transactions stg_transaction_rejections")
    with duckdb.connect(str(database_path), read_only=True) as connection:
        accepted = connection.execute("select count(*) from analytics.stg_transactions").fetchone()[0]
        rejected = connection.execute("select count(*) from analytics.stg_transaction_rejections").fetchone()[0]
        currencies = connection.execute("select distinct currency from analytics.stg_transactions order by 1").fetchall()
    assert accepted == 864
    assert rejected == 0
    assert currencies == [("AED",), ("PKR",)]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest apps/api/tests/test_analytics_models.py::test_dbt_builds_staging_models_from_active_imports -v`

Expected: FAIL because the `dbt` executable and analytics project do not exist.

- [ ] **Step 3: Add the smallest project configuration and dependency changes**

Add the two dev dependencies. Keep them out of `dependencies` because Docker production images use `uv sync --no-dev`.

```toml
[dependency-groups]
dev = [
  "dbt-core>=1.9,<2.0",
  "dbt-duckdb>=1.9,<2.0",
  "httpx>=0.27,<1.0",
  "pytest>=8.0,<9.0",
  "reportlab>=4.2,<5.0",
  "ruff>=0.12,<1.0",
]
```

Create `analytics/dbt_project.yml` and `analytics/profiles.yml`:

```yaml
# dbt_project.yml
name: spend_memory_analytics
version: "1.0"
config-version: 2
profile: spend_memory_analytics
model-paths: ["models"]
macro-paths: ["macros"]
seed-paths: ["seeds"]
test-paths: ["tests"]
models:
  spend_memory_analytics:
    +schema: analytics
    +materialized: table
```

```yaml
# profiles.yml
spend_memory_analytics:
  target: local
  outputs:
    local:
      type: duckdb
      path: "{{ env_var('SPEND_MEMORY_DUCKDB_PATH') }}"
      schema: analytics
      threads: 1
```

Run `uv lock` after the `pyproject.toml` edit. Add these exact Makefile targets and README example:

```make
analytics:
	SPEND_MEMORY_DUCKDB_PATH=$${SPEND_MEMORY_DUCKDB_PATH:?set a local DuckDB path} uv run dbt build --project-dir analytics --profiles-dir analytics

analytics-test:
	uv run pytest apps/api/tests/test_analytics_models.py -v
```

```sh
SPEND_MEMORY_DUCKDB_PATH=/absolute/path/to/local.duckdb make analytics
```

- [ ] **Step 4: Implement source declarations, macros, and staging models**

Declare the three tables with `schema: main`, and source freshness on `source_documents` with `warn_after: {count: 30, period: day}` and `error_after: {count: 90, period: day}` using `loaded_at_field: created_at`. The active relation is the only way staging reads raw data:

```sql
-- analytics/macros/active_raw_transactions.sql
{% macro active_raw_transactions() %}
select
  raw.raw_transaction_id,
  raw.import_run_id,
  run.document_id,
  document.original_filename,
  run.parser_id,
  run.parser_version,
  raw.source_ordinal,
  raw.date_text,
  raw.description_text,
  raw.amount_text,
  raw.normalized_amount_text,
  raw.currency_text,
  raw.source_page,
  raw.source_row,
  raw.source_text,
  raw.extraction_method,
  raw.raw_account_identity,
  raw.raw_account_reference,
  raw.raw_balance_text,
  raw.extraction_confidence
from {{ source('spend_memory', 'raw_transactions') }} as raw
join {{ source('spend_memory', 'import_runs') }} as run on raw.import_run_id = run.run_id
join {{ source('spend_memory', 'source_documents') }} as document on run.document_id = document.document_id
where run.is_active = true
{% endmacro %}
```

Use `coalesce(normalized_amount_text, amount_text)` for the parsed input. The reusable amount expression removes an optional AED or PKR marker and requires an integer with optional leading sign:

```sql
-- analytics/macros/money.sql
{% macro normalized_amount_text(column_name) %}
trim(regexp_replace({{ column_name }}, '^(AED|PKR)\\s*', ''))
{% endmacro %}

{% macro amount_is_integer(column_name) %}
regexp_full_match({{ normalized_amount_text(column_name) }}, '[+-]?[0-9]+')
{% endmacro %}

{% macro amount_minor(column_name) %}
abs(cast({{ normalized_amount_text(column_name) }} as bigint))
{% endmacro %}

{% macro direction(column_name) %}
case when cast({{ normalized_amount_text(column_name) }} as bigint) < 0 then 'debit' else 'credit' end
{% endmacro %}
```

Each parser-family model filters only its own parser ID and selects the active relation. `stg_transactions.sql` must union them, calculate `is_valid`, and only calculate amounts when `amount_is_integer` is true:

```sql
with parser_rows as (
  select * from {{ ref('stg_canonical_csv_transactions') }}
  union all select * from {{ ref('stg_synthetic_aed_pdf_transactions') }}
  union all select * from {{ ref('stg_synthetic_pkr_pdf_transactions') }}
), evaluated as (
  select *,
    try_strptime(date_text, '%Y-%m-%d')::date as transaction_date,
    trim(description_text) as description,
    upper(trim(currency_text)) as currency,
    {{ amount_is_integer("coalesce(normalized_amount_text, amount_text)") }} as amount_is_valid
  from parser_rows
)
select *,
  raw_account_identity as account_identity,
  case when transaction_date is not null and description <> '' and currency in ('AED', 'PKR')
            and amount_is_valid and raw_account_identity is not null and trim(raw_account_identity) <> ''
       then {{ amount_minor("coalesce(normalized_amount_text, amount_text)") }} end as amount_minor,
  case when transaction_date is not null and description <> '' and currency in ('AED', 'PKR')
            and amount_is_valid and raw_account_identity is not null and trim(raw_account_identity) <> ''
       then {{ direction("coalesce(normalized_amount_text, amount_text)") }} end as direction,
  case when transaction_date is not null and description <> '' and currency in ('AED', 'PKR')
            and amount_is_valid and raw_account_identity is not null and trim(raw_account_identity) <> ''
       then case when {{ direction("coalesce(normalized_amount_text, amount_text)") }} = 'debit'
                 then -{{ amount_minor("coalesce(normalized_amount_text, amount_text)") }}
                 else {{ amount_minor("coalesce(normalized_amount_text, amount_text)") }} end end as net_amount_minor,
  case when transaction_date is not null and description <> '' and currency in ('AED', 'PKR')
            and amount_is_valid and raw_account_identity is not null and trim(raw_account_identity) <> ''
       then true else false end as is_valid
from evaluated
```

`stg_transaction_rejections.sql` selects `is_valid = false` and uses this ordered reason expression: `invalid_date`, `missing_description`, `unsupported_currency`, `invalid_amount`, `missing_account_identity`. Add schema tests for unique `raw_transaction_id`, not-null descriptions, accepted currencies, accepted directions, accepted parser IDs, and a relationship test back to `raw_transactions`.

- [ ] **Step 5: Run focused and full checks**

Run:

```sh
uv run pytest apps/api/tests/test_analytics_models.py::test_dbt_builds_staging_models_from_active_imports -v
uv run pytest apps/api/tests -v
uv run ruff check apps/api sample_data
```

Expected: all selected tests pass, including the 864 accepted synthetic rows and no synthetic rejections.

- [ ] **Step 6: Commit and push the independently working staging layer**

```sh
git add analytics pyproject.toml uv.lock Makefile README.md apps/api/tests/test_analytics_models.py
git commit -m "clean transactions"
git push -u origin feature/analytics-models
```

## Task 2: Add deterministic controls and reconciliation evidence

**Files:**
- Modify: `sample_data/generator/generate.py`
- Create: `analytics/seeds/import_controls.csv`
- Create: `analytics/models/intermediate/int_duplicate_candidates.sql`
- Create: `analytics/models/intermediate/int_running_balance_checks.sql`
- Create: `analytics/models/intermediate/int_import_reconciliation.sql`
- Create: `analytics/models/intermediate/intermediate.yml`
- Modify: `apps/api/tests/test_analytics_models.py`

**Interfaces:**
- Consumes: `analytics.stg_transactions`, generated `import_controls` seed columns `original_filename`, `account_identity`, `currency`, and `expected_net_amount_minor`.
- Produces: `analytics.int_duplicate_candidates`, `analytics.int_running_balance_checks`, and `analytics.int_import_reconciliation` with one row per active import and status `reconciled`, `unreconciled`, or `not_available`.

- [ ] **Step 1: Write failing reconciliation tests**

Add these assertions after the staging test:

```python
def test_dbt_marks_matching_synthetic_imports_reconciled(tmp_path: Path) -> None:
    database_path = _build_fixture_database(tmp_path)
    _dbt_build(database_path, "int_import_reconciliation")
    with duckdb.connect(str(database_path), read_only=True) as connection:
        statuses = connection.execute(
            "select reconciliation_status, count(*) from analytics.int_import_reconciliation group by 1 order by 1"
        ).fetchall()
    assert statuses == [("reconciled", 3)]


def test_duplicate_candidates_keep_every_transaction(tmp_path: Path) -> None:
    database_path = _build_fixture_database(tmp_path)
    _dbt_build(database_path, "int_duplicate_candidates")
    with duckdb.connect(str(database_path), read_only=True) as connection:
        staged = connection.execute("select count(*) from analytics.stg_transactions").fetchone()[0]
        candidates = connection.execute("select count(*) from analytics.int_duplicate_candidates").fetchone()[0]
    assert staged == 864
    assert candidates >= 2
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest apps/api/tests/test_analytics_models.py -k 'reconciled or duplicate_candidates' -v`

Expected: FAIL because the seed and intermediate models do not exist.

- [ ] **Step 3: Generate and commit source controls from the canonical ledger**

Extend `_reconcile` so it totals signed integer `amount_minor` by `(source_document, account_id, currency)`, then write `expected/import_controls.csv` alongside the ledger. Its exact headers are:

```csv
original_filename,account_identity,currency,expected_net_amount_minor
aed_january_2026.csv,AED-SYNTH-001,AED,-152616
```

Do not copy the illustrative row above as a fixed value. In the generator, derive every row from `transactions`, sort by all three key columns, write the full CSV to `expected/import_controls.csv`, and copy that generated file to `analytics/seeds/import_controls.csv` in the fixture refresh command. Add a generator test that regenerates twice and asserts byte-for-byte identical controls and that the control total equals the ledger total per source, account, and currency.

- [ ] **Step 4: Implement intermediate models with preserved evidence**

Use self-join criteria of account, currency, amount, date, and normalized description. `int_duplicate_candidates` must return both raw IDs in sorted order, `candidate_score = 100`, and `candidate_reason = 'same_date_same_amount_same_description'`; it must not filter or mutate `stg_transactions`.

Use `try_cast(regexp_replace(raw_balance_text, '[^0-9+-]', '', 'g') as bigint)` for a parsed balance. `int_running_balance_checks` partitions by `import_run_id, account_identity`, orders by `transaction_date, source_ordinal`, and returns `not_available` when either adjacent balance is missing. For available adjacent balances, check `current_balance = previous_balance + net_amount_minor` and return `pass` or `fail`.

`int_import_reconciliation` groups source totals by `import_run_id, original_filename, account_identity, currency`, left joins `{{ ref('import_controls') }}`, and left joins balance failures. Its status expression is:

```sql
case
  when control.expected_net_amount_minor is null then 'not_available'
  when source.net_amount_minor <> control.expected_net_amount_minor then 'unreconciled'
  when coalesce(balance.has_failed_balance_check, false) then 'unreconciled'
  else 'reconciled'
end as reconciliation_status
```

Add schema tests for accepted statuses, unique `(import_run_id, account_identity, currency)`, non-null evidence totals, and relationships to staging imports. Add a singular test that fails if a `reconciled` row has a non-null expected total different from the observed total.

- [ ] **Step 5: Run focused and full checks**

Run:

```sh
uv run pytest apps/api/tests/test_sample_data.py apps/api/tests/test_analytics_models.py -v
SPEND_MEMORY_DUCKDB_PATH=/tmp/spend-memory-analytics.duckdb uv run dbt build --project-dir analytics --profiles-dir analytics
uv run ruff check apps/api sample_data
```

Expected: tests pass, the full dbt build completes, matching synthetic sources are reconciled, and candidate rows do not reduce transaction count.

- [ ] **Step 6: Commit and push reconciliation**

```sh
git add analytics sample_data apps/api/tests/test_analytics_models.py
git commit -m "check balances"
git push
```

## Task 3: Build trusted marts and exact period comparisons

**Files:**
- Create: `analytics/models/marts/mart_transactions.sql`
- Create: `analytics/models/marts/mart_merchants.sql`
- Create: `analytics/models/marts/mart_categories.sql`
- Create: `analytics/models/marts/mart_recurring_groups.sql`
- Create: `analytics/models/marts/mart_monthly_summary.sql`
- Create: `analytics/models/marts/mart_category_summary.sql`
- Create: `analytics/models/marts/mart_period_comparisons.sql`
- Create: `analytics/models/marts/marts.yml`
- Create: `analytics/tests/trusted_marts_only_reconciled.sql`
- Create: `analytics/tests/period_comparison_contributions_reconcile.sql`
- Modify: `apps/api/tests/test_analytics_models.py`

**Interfaces:**
- Consumes: valid `stg_transactions` and `int_import_reconciliation`.
- Produces: trusted transaction rows and account-and-currency scoped summaries. `mart_period_comparisons` has one debit or credit contribution row per account, currency, and comparable month: `account_identity`, `currency`, `period_start`, `previous_period_start`, `direction`, `before_net_amount_minor`, `after_net_amount_minor`, `difference_net_amount_minor`, and `observed_period_difference_minor`.

- [ ] **Step 1: Write failing mart contract tests**

Add these tests:

```python
def test_trusted_marts_match_the_canonical_ledger(tmp_path: Path) -> None:
    database_path = _build_fixture_database(tmp_path)
    _dbt_build(database_path, "mart_transactions mart_monthly_summary mart_period_comparisons")
    with duckdb.connect(str(database_path), read_only=True) as connection:
        transaction_count = connection.execute("select count(*) from analytics.mart_transactions").fetchone()[0]
        total = connection.execute("select sum(net_amount_minor) from analytics.mart_transactions").fetchone()[0]
        currencies = connection.execute("select distinct currency from analytics.mart_monthly_summary order by 1").fetchall()
    assert transaction_count == 864
    assert total == -114355263
    assert currencies == [("AED",), ("PKR",)]


def test_unreconciled_import_is_excluded_from_trusted_marts(tmp_path: Path) -> None:
    database_path = _build_fixture_database(tmp_path)
    with duckdb.connect(str(database_path)) as connection:
        connection.execute("update raw_transactions set amount_text = '-999999999' where source_ordinal = 1")
    _dbt_build(database_path, "mart_transactions")
    with duckdb.connect(str(database_path), read_only=True) as connection:
        statuses = connection.execute("select distinct reconciliation_status from analytics.int_import_reconciliation").fetchall()
        count = connection.execute("select count(*) from analytics.mart_transactions").fetchone()[0]
    assert ("unreconciled",) in statuses
    assert count < 864
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest apps/api/tests/test_analytics_models.py -k 'trusted_marts or unreconciled_import' -v`

Expected: FAIL because no mart models exist.

- [ ] **Step 3: Implement the seven mart contracts**

Create `mart_transactions` as valid staging rows inner joined to reconciliation rows with `reconciliation_status = 'reconciled'`. Keep raw transaction ID, import run ID, document ID, parser metadata, source coordinates, raw fields, canonical money fields, and account identity. Add nullable `merchant_id`, `category_id`, and `recurring_group_id`, plus literal `enrichment_version = 'unavailable'`.

Create `mart_merchants`, `mart_categories`, and `mart_recurring_groups` with their documented future columns and `where false`, so they have stable zero-row shapes without inventing enrichments. `mart_category_summary` groups trusted transactions by account, currency, `category_id`, and `coalesce(category_id, 'uncategorized') as category_label`, retaining `sum(net_amount_minor)` as an integer.

Use this aggregate shape for monthly summaries:

```sql
select
  account_identity,
  currency,
  date_trunc('month', transaction_date)::date as period_start,
  direction,
  count(*) as transaction_count,
  sum(amount_minor)::bigint as amount_minor,
  sum(net_amount_minor)::bigint as net_amount_minor
from {{ ref('mart_transactions') }}
group by 1, 2, 3, 4
```

Build one monthly total CTE grouped by account, currency, and period, then a contribution CTE grouped by account, currency, period, and direction. Use `lag(net_amount_minor) over (partition by account_identity, currency, direction order by period_start)` for a contribution's previous amount and `lag(net_amount_minor) over (partition by account_identity, currency order by period_start)` for the observed total's previous amount. `mart_period_comparisons` includes one debit and credit row for each period having a prior total, `before_net_amount_minor`, `after_net_amount_minor`, `difference_net_amount_minor = after - before`, and `observed_period_difference_minor = total_after - total_before`. It has no fabricated merchant or category attribution in this milestone.

Add schema tests for unique transaction IDs, non-null lineage, accepted currencies, accepted directions, non-null period keys, and unique comparison `(account_identity, currency, period_start, direction)`. The singular test `trusted_marts_only_reconciled.sql` joins mart transactions to reconciliation and returns any row whose status is not `reconciled`. `period_comparison_contributions_reconcile.sql` groups comparison rows by account, currency, and period, then returns a group when `sum(difference_net_amount_minor) <> max(observed_period_difference_minor)`.

- [ ] **Step 4: Run focused and full verification**

Run:

```sh
uv run pytest apps/api/tests/test_analytics_models.py -v
SPEND_MEMORY_DUCKDB_PATH=/tmp/spend-memory-analytics.duckdb uv run dbt build --project-dir analytics --profiles-dir analytics
uv run pytest apps/api/tests -v
uv run ruff check apps/api sample_data
pnpm --dir apps/web test --run
pnpm --dir apps/web lint
```

Expected: all tests pass, dbt tests pass, trusted summaries remain currency-scoped, and a deliberately altered source row makes its import unreconciled and absent from trusted marts.

- [ ] **Step 5: Commit and push analytics marts**

```sh
git add analytics apps/api/tests/test_analytics_models.py
git commit -m "add analytics"
git push
```

## Final Milestone Verification

- [ ] **Step 1: Verify repository state and the full check suite**

Run:

```sh
git status --short
git log --oneline origin/main..HEAD
uv run pytest apps/api/tests -v
uv run ruff check apps/api sample_data
pnpm --dir apps/web test --run
pnpm --dir apps/web lint
SPEND_MEMORY_DUCKDB_PATH=/tmp/spend-memory-analytics.duckdb uv run dbt build --project-dir analytics --profiles-dir analytics
```

Expected: no unexpected worktree changes, only the planned feature commits are ahead of `origin/main`, and every command exits with status 0.

- [ ] **Step 2: Review before merge**

Confirm that no source table, original statement, raw value, API route, UI route, ML dependency, or hosted service changed. Compare `mart_transactions` against the canonical ledger by account and currency, and confirm the singular dbt tests prove trusted-only and exact period-difference behavior.

## Plan Self-Review

**Spec coverage:** Task 1 covers local dbt configuration, source freshness, active-run filtering, parser families, raw lineage, explicit amount correction, validation, rejection, and canonical money. Task 2 covers generated controls, duplicate evidence, running balances, all three reconciliation statuses, and no destructive deduplication. Task 3 covers all seven mart contracts, trusted-mart exclusion, separate currencies, integer aggregates, placeholder-free enrichment dimensions, and debit and credit contribution rows whose exact sum equals each observed period change. The final verification covers local-only operation and all required checks.

**Placeholder scan:** This plan contains no unfinished markers or generic implementation directions. Every code change is paired with an explicit target, behavior, command, and expected result.

**Type consistency:** Staging exposes `raw_transaction_id`, `import_run_id`, `document_id`, `account_identity`, `currency`, `amount_minor`, `direction`, and `net_amount_minor`. Intermediate models consume those names and expose `reconciliation_status`. Marts consume the same names and retain their lineage; all period totals stay `BIGINT`.
