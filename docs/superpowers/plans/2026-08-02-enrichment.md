# Milestone 4 Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build local, evidence-backed enrichment that makes reconciled transactions easier to understand without changing financial facts.

**Architecture:** Enrichment is a Python domain package backed by small DuckDB tables. It reads only `analytics.mart_transactions`, which already excludes unreconciled imports, then writes local correction records and review candidates with source IDs, confidence, evidence, and a method version. dbt joins only confirmed annotations into analytics marts, while a pure Python period service creates exact template explanations from integer-minor-unit aggregates.

**Tech Stack:** Python 3.12, DuckDB, dbt-duckdb, pytest, standard-library text scoring and parsing.

## Global Constraints

- Keep statement documents, raw transactions, and canonical money values immutable.
- Read enrichment input only from reconciled `analytics.mart_transactions` rows.
- Store and calculate money as integer minor units. Never use ML or floating point for monetary totals.
- Keep all financial data, corrections, search, and inference local. Do not add online calls, external datasets, reference packs, hosted models, or remote model downloads.
- Use synthetic fixtures only in tests. Do not commit a real statement or user correction.
- Confirmed transaction overrides and confirmed merchant aliases are facts. Suggestions and review candidates are not facts and must not alter totals.
- Use rules and standard-library code first. Add no ML dependency unless a later measured evaluation proves it beats its explicit baseline.
- Do not add HTTP routes or UI work in this milestone. Milestone 5 owns the API and interface.
- Follow TDD. Run the relevant focused test before and after each change, then run `make test`, `make lint`, and the analytics build before handing off.
- Keep commits short, natural, and free of AI attribution. Push each finished commit.

---

## File structure

- `apps/api/spend_memory/storage/repository.py`: exports the existing database writer lock for the enrichment repository.
- `apps/api/spend_memory/storage/migrations/0003_enrichment.sql`: creates local merchant, category, annotation, and review-candidate tables.
- `apps/api/spend_memory/enrichment/models.py`: typed immutable records shared by every enrichment component.
- `apps/api/spend_memory/enrichment/repository.py`: one focused persistence boundary for corrections, trusted transactions, and review candidates.
- `apps/api/spend_memory/enrichment/normalization.py`: documented descriptor normalization with no database access.
- `apps/api/spend_memory/enrichment/merchants.py`: local exact-alias resolution and character n-gram TF-IDF suggestions.
- `apps/api/spend_memory/enrichment/categories.py`: deterministic category-precedence resolver.
- `apps/api/spend_memory/enrichment/recurring.py`: rules for recurring-payment candidates.
- `apps/api/spend_memory/enrichment/review.py`: duplicate and unusual-spend candidate rules.
- `apps/api/spend_memory/enrichment/search.py`: structured-filter parser and deterministic lexical search.
- `apps/api/spend_memory/enrichment/periods.py`: exact period-comparison decomposition and fixed-language explanation.
- `apps/api/spend_memory/enrichment/service.py`: explicit local refresh orchestration, called by tests now and by Milestone 5 later.
- `apps/api/tests/test_enrichment_repository.py`: migration, lineage, and correction persistence coverage.
- `apps/api/tests/test_merchant_resolution.py`, `test_category_resolution.py`, `test_recurring_candidates.py`, `test_review_candidates.py`, `test_transaction_search.py`, and `test_period_explanations.py`: behaviour-first synthetic tests for each domain unit.
- `apps/api/tests/test_enrichment_service.py`: end-to-end local refresh against a reconciled dbt fixture.
- `apps/api/tests/test_analytics_models.py`: verifies confirmed enrichment reaches dbt marts while suggestions remain non-factual.
- `analytics/models/sources.yml`, `analytics/models/marts/mart_transactions.sql`, `analytics/models/marts/mart_merchants.sql`, `analytics/models/marts/mart_categories.sql`, `analytics/models/marts/mart_recurring_groups.sql`, `analytics/models/marts/mart_category_summary.sql`, and `analytics/models/marts/marts.yml`: expose confirmed local enrichment to analytics without changing source totals.
- `docs/architecture.md`: documents local-only enrichment boundaries, confidence meaning, and the Milestone 5 API handoff.

## Shared interfaces

Every task uses these concrete records from `apps/api/spend_memory/enrichment/models.py`:

```python
from dataclasses import dataclass
from datetime import date
from uuid import UUID


@dataclass(frozen=True)
class TrustedTransaction:
    raw_transaction_id: UUID
    account_identity: str | None
    transaction_date: date
    description: str
    normalized_description: str
    currency: str
    amount_minor: int
    direction: str


@dataclass(frozen=True)
class MerchantMatch:
    merchant_id: UUID | None
    merchant_name: str | None
    status: str
    confidence: float
    method: str
    evidence: dict[str, str | float]


@dataclass(frozen=True)
class CategoryDecision:
    category_id: UUID | None
    category_label: str
    source: str


@dataclass(frozen=True)
class SearchResult:
    transaction: TrustedTransaction
    score: float


@dataclass(frozen=True)
class PeriodExplanation:
    before_net_amount_minor: int
    after_net_amount_minor: int
    difference_net_amount_minor: int
    contribution_total_minor: int
    remainder_minor: int
    text: str


@dataclass(frozen=True)
class RecurringCandidate:
    candidate_key: str
    account_identity: str | None
    merchant_id: UUID | None
    normalized_descriptor: str
    currency: str
    direction: str
    cadence: str
    first_transaction_date: date
    last_transaction_date: date
    amount_min_minor: int
    amount_max_minor: int
    expected_next_start: date
    expected_next_end: date
    confidence: float
    evidence: dict[str, str | int | float]


@dataclass(frozen=True)
class DuplicateCandidate:
    raw_transaction_ids: tuple[UUID, UUID]
    confidence: float
    evidence: dict[str, str | int | float]


@dataclass(frozen=True)
class UnusualSpendCandidate:
    raw_transaction_id: UUID
    confidence: float
    evidence: dict[str, str | int | float]


@dataclass(frozen=True)
class SearchQuery:
    after: date | None = None
    before: date | None = None
    currency: str | None = None
    direction: str | None = None
    merchant: str | None = None
    category: str | None = None
    amount_min_minor: int | None = None
    amount_max_minor: int | None = None
    state: str | None = None
    text: str = ""


@dataclass(frozen=True)
class MerchantEvaluation:
    precision: float
    recall: float
    coverage: float
    expected_calibration_error: float
```

### Task 1: Add migration-backed enrichment storage

**Files:**

- Create: `apps/api/spend_memory/storage/migrations/0003_enrichment.sql`
- Create: `apps/api/spend_memory/enrichment/__init__.py`
- Create: `apps/api/spend_memory/enrichment/models.py`
- Create: `apps/api/spend_memory/enrichment/repository.py`
- Modify: `apps/api/spend_memory/storage/repository.py:78-106`
- Test: `apps/api/tests/test_enrichment_repository.py`

**Interfaces:**

- Consumes: `apply_migrations(database_path)` and `analytics.mart_transactions` built by dbt.
- Produces: `EnrichmentRepository`, including `create_merchant`, `confirm_alias`, `create_category`, `assign_merchant_category`, `set_transaction_category_override`, `list_trusted_transactions`, and candidate replacement methods used in Tasks 2 through 8.

- [ ] **Step 1: Write the failing migration and repository tests**

```python
def test_enrichment_migration_is_idempotent_and_keeps_annotations_local(tmp_path: Path) -> None:
    database_path = tmp_path / "spend-memory.duckdb"
    repository = EnrichmentRepository(database_path)
    repository.apply_migrations()

    with duckdb.connect(str(database_path), read_only=True) as connection:
        tables = {row[0] for row in connection.execute("show tables").fetchall()}
        assert {"merchants", "merchant_aliases", "categories", "transaction_merchant_annotations"} <= tables
        assert "amount_minor" not in {
            row[1] for row in connection.execute("pragma_table_info('transaction_merchant_annotations')").fetchall()
        }


def test_confirmed_alias_and_transaction_override_keep_lineage(tmp_path: Path) -> None:
    repository = EnrichmentRepository(tmp_path / "spend-memory.duckdb")
    merchant = repository.create_merchant("MetroMart")
    repository.confirm_alias("METRO MART", merchant.merchant_id)
    category = repository.create_category("Groceries")
    transaction_id = uuid4()
    repository.set_transaction_category_override(transaction_id, category.category_id)

    assert repository.find_confirmed_alias("metro mart").merchant_id == merchant.merchant_id
    assert repository.find_transaction_category_override(transaction_id) == category
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `uv run pytest apps/api/tests/test_enrichment_repository.py -v`

Expected: FAIL because `spend_memory.enrichment` and migration `0003_enrichment.sql` do not exist.

- [ ] **Step 3: Create the immutable shared records and migration**

Create `models.py` with the shared records above plus these persistence records:

```python
@dataclass(frozen=True)
class Merchant:
    merchant_id: UUID
    merchant_name: str


@dataclass(frozen=True)
class Category:
    category_id: UUID
    category_label: str
```

Create `0003_enrichment.sql` with tables that reference source IDs rather than copying financial fields:

```sql
CREATE TABLE merchants (
    merchant_id UUID PRIMARY KEY,
    merchant_name VARCHAR NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT current_timestamp
);

CREATE TABLE merchant_aliases (
    merchant_alias_id UUID PRIMARY KEY,
    normalized_descriptor VARCHAR NOT NULL UNIQUE,
    merchant_id UUID NOT NULL REFERENCES merchants(merchant_id),
    confirmed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT current_timestamp
);

CREATE TABLE merchant_currency_observations (
    merchant_id UUID NOT NULL REFERENCES merchants(merchant_id),
    currency VARCHAR NOT NULL,
    first_confirmed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT current_timestamp,
    PRIMARY KEY (merchant_id, currency)
);

CREATE TABLE categories (
    category_id UUID PRIMARY KEY,
    category_label VARCHAR NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT current_timestamp
);

CREATE TABLE merchant_category_assignments (
    merchant_id UUID PRIMARY KEY REFERENCES merchants(merchant_id),
    category_id UUID NOT NULL REFERENCES categories(category_id),
    confirmed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT current_timestamp
);

CREATE TABLE transaction_category_overrides (
    raw_transaction_id UUID PRIMARY KEY REFERENCES raw_transactions(raw_transaction_id),
    category_id UUID NOT NULL REFERENCES categories(category_id),
    confirmed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT current_timestamp
);

CREATE TABLE transaction_merchant_annotations (
    raw_transaction_id UUID PRIMARY KEY REFERENCES raw_transactions(raw_transaction_id),
    merchant_id UUID REFERENCES merchants(merchant_id),
    resolution_status VARCHAR NOT NULL,
    confidence DOUBLE NOT NULL,
    method VARCHAR NOT NULL,
    evidence_json VARCHAR NOT NULL,
    enrichment_version VARCHAR NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT current_timestamp,
    CHECK (resolution_status IN ('confirmed', 'suggested', 'unresolved')),
    CHECK (confidence >= 0 AND confidence <= 1)
);

CREATE TABLE recurring_candidates (
    recurring_candidate_id UUID PRIMARY KEY,
    candidate_key VARCHAR NOT NULL UNIQUE,
    account_identity VARCHAR,
    merchant_id UUID REFERENCES merchants(merchant_id),
    normalized_descriptor VARCHAR NOT NULL,
    currency VARCHAR NOT NULL,
    direction VARCHAR NOT NULL,
    cadence VARCHAR NOT NULL,
    first_transaction_date DATE NOT NULL,
    last_transaction_date DATE NOT NULL,
    amount_min_minor BIGINT NOT NULL,
    amount_max_minor BIGINT NOT NULL,
    expected_next_start DATE NOT NULL,
    expected_next_end DATE NOT NULL,
    confidence DOUBLE NOT NULL,
    evidence_json VARCHAR NOT NULL,
    status VARCHAR NOT NULL DEFAULT 'candidate',
    enrichment_version VARCHAR NOT NULL,
    CHECK (direction IN ('debit', 'credit')),
    CHECK (cadence IN ('weekly', 'monthly', 'quarterly', 'annual')),
    CHECK (status = 'candidate')
);

CREATE TABLE duplicate_review_candidates (
    duplicate_candidate_id UUID PRIMARY KEY,
    first_raw_transaction_id UUID NOT NULL REFERENCES raw_transactions(raw_transaction_id),
    second_raw_transaction_id UUID NOT NULL REFERENCES raw_transactions(raw_transaction_id),
    confidence DOUBLE NOT NULL,
    evidence_json VARCHAR NOT NULL,
    enrichment_version VARCHAR NOT NULL,
    UNIQUE (first_raw_transaction_id, second_raw_transaction_id),
    CHECK (first_raw_transaction_id < second_raw_transaction_id),
    CHECK (confidence >= 0 AND confidence <= 1)
);

CREATE TABLE unusual_spend_candidates (
    unusual_candidate_id UUID PRIMARY KEY,
    raw_transaction_id UUID NOT NULL UNIQUE REFERENCES raw_transactions(raw_transaction_id),
    confidence DOUBLE NOT NULL,
    evidence_json VARCHAR NOT NULL,
    enrichment_version VARCHAR NOT NULL,
    CHECK (confidence >= 0 AND confidence <= 1)
);
```

- [ ] **Step 4: Implement the small repository boundary**

Rename `_database_write_lock` to `database_write_lock` in `storage/repository.py` and update its existing callers. In `enrichment/repository.py`, use that lock with parameterized DuckDB queries. The public constructor and confirmed-alias methods must have these signatures:

```python
class EnrichmentRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)
        apply_migrations(self.database_path)

    def create_merchant(self, merchant_name: str) -> Merchant: ...
    def confirm_alias(self, descriptor: str, merchant_id: UUID) -> None: ...
    def record_confirmed_merchant_currency(self, merchant_id: UUID, currency: str) -> None: ...
    def find_confirmed_alias(self, descriptor: str) -> Merchant | None: ...
    def create_category(self, category_label: str) -> Category: ...
    def assign_merchant_category(self, merchant_id: UUID, category_id: UUID) -> None: ...
    def find_merchant_category(self, merchant_id: UUID) -> Category | None: ...
    def set_transaction_category_override(self, raw_transaction_id: UUID, category_id: UUID) -> None: ...
    def find_transaction_category_override(self, raw_transaction_id: UUID) -> Category | None: ...
    def save_merchant_annotation(self, raw_transaction_id: UUID, match: MerchantMatch) -> None: ...
```

Validate that names and descriptors are non-empty after trimming. Serialize evidence with `json.dumps(..., sort_keys=True)`. All writers use one transaction inside `database_write_lock`.

- [ ] **Step 5: Run focused storage tests**

Run: `uv run pytest apps/api/tests/test_enrichment_repository.py apps/api/tests/test_storage_repository.py -v`

Expected: PASS, including existing transactional migration tests.

- [ ] **Step 6: Commit and push**

```bash
git add apps/api/spend_memory/storage/repository.py apps/api/spend_memory/storage/migrations/0003_enrichment.sql apps/api/spend_memory/enrichment apps/api/tests/test_enrichment_repository.py
git commit -m "store enrichment"
git push -u origin HEAD
```

### Task 2: Normalize descriptors and resolve local merchants

**Files:**

- Create: `apps/api/spend_memory/enrichment/normalization.py`
- Create: `apps/api/spend_memory/enrichment/merchants.py`
- Modify: `apps/api/spend_memory/enrichment/repository.py`
- Test: `apps/api/tests/test_merchant_resolution.py`

**Interfaces:**

- Consumes: `Merchant`, confirmed aliases, and `TrustedTransaction` from Task 1.
- Produces: `normalize_descriptor(value: str) -> str` and `MerchantResolver.resolve(transaction: TrustedTransaction) -> MerchantMatch` for Tasks 4, 5, and 9.

- [ ] **Step 1: Write failing normalization and resolution tests**

```python
def test_normalize_descriptor_removes_known_statement_noise() -> None:
    assert normalize_descriptor("POS METRO-MART #A9172 TERM 004") == "metro mart"


def test_exact_confirmed_alias_is_a_confirmed_match(repository: EnrichmentRepository) -> None:
    merchant = repository.create_merchant("MetroMart")
    repository.confirm_alias("METRO MART", merchant.merchant_id)

    result = MerchantResolver(repository).resolve(_transaction("MetroMart POS"))

    assert result == MerchantMatch(
        merchant.merchant_id,
        "MetroMart",
        "confirmed",
        1.0,
        "confirmed_alias",
        {"normalized_descriptor": "metro mart"},
    )


def test_retrieval_is_a_suggestion_and_never_a_confirmed_fact(repository: EnrichmentRepository) -> None:
    merchant = repository.create_merchant("MetroMart")
    repository.confirm_alias("METRO MART", merchant.merchant_id)

    result = MerchantResolver(repository).resolve(_transaction("METRO MART ONLINE"))

    assert result.status == "suggested"
    assert result.merchant_id == merchant.merchant_id
    assert 0 < result.confidence < 1
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `uv run pytest apps/api/tests/test_merchant_resolution.py -v`

Expected: FAIL because normalization and `MerchantResolver` do not exist.

- [ ] **Step 3: Implement explicit normalization**

Use only these transformations, in this order, so the behavior remains inspectable:

```python
_PREFIX = re.compile(r"^(?:pos|card|debit|payment|purchase|online)\\s+", re.I)
_TERMINAL = re.compile(r"\\s+(?:term(?:inal)?|txn|ref|id|#)\\s*[a-z0-9-]+(?:\\s+|$)", re.I)
_PUNCTUATION = re.compile(r"[^a-z0-9]+")


def normalize_descriptor(value: str) -> str:
    normalized = _PREFIX.sub("", value.strip())
    normalized = _TERMINAL.sub(" ", normalized)
    normalized = _PUNCTUATION.sub(" ", normalized.lower())
    return " ".join(normalized.split())
```

Add test cases for empty input, payment prefixes, terminal fragments, punctuation, and an identifier embedded in a genuine merchant name. Keep every exception in a test before broadening a regex.

- [ ] **Step 4: Implement standard-library character n-gram TF-IDF retrieval**

Use `collections.Counter` and `math.log`, not a new dependency. Build trigrams from padded normalized text, calculate document frequency across local confirmed aliases and merchant names, then cosine similarity. Add a small currency compatibility bonus only when `merchant_currency_observations` contains the transaction currency for that candidate merchant. The resolver chooses:

```python
if exact is not None:
    return MerchantMatch(exact.merchant_id, exact.merchant_name, "confirmed", 1.0, "confirmed_alias", evidence)
if best_score >= 0.82:
    return MerchantMatch(best.merchant_id, best.merchant_name, "suggested", round(best_score, 4), "char_ngram_tfidf", evidence)
return MerchantMatch(None, None, "unresolved", 0.0, "none", {"normalized_descriptor": normalized})
```

Record a candidate's normalized descriptor, winning alias, text score, and any currency signal in `evidence`. Do not write an alias from a suggestion.

- [ ] **Step 5: Add leakage-safe evaluation fixtures and run merchant tests**

Create synthetic groups where each merchant's descriptor variants stay together. Define `evaluate_merchant_matches(examples, held_out_merchant_ids) -> MerchantEvaluation`. It must split by `merchant_id`, report precision, recall, coverage, and expected calibration error using five fixed confidence buckets. Include an assertion that a held-out MetroMart variant never appears in the retrieval corpus as a MetroMart alias.

```python
evaluation = evaluate_merchant_matches(examples, held_out_merchant_ids={metromart_id})
assert evaluation.precision == 1.0
assert evaluation.coverage == 0.5
assert evaluation.expected_calibration_error >= 0.0
```

Run: `uv run pytest apps/api/tests/test_merchant_resolution.py -v`

Expected: PASS.

- [ ] **Step 6: Commit and push**

```bash
git add apps/api/spend_memory/enrichment/normalization.py apps/api/spend_memory/enrichment/merchants.py apps/api/spend_memory/enrichment/repository.py apps/api/tests/test_merchant_resolution.py
git commit -m "resolve merchants locally"
git push
```

### Task 3: Apply deterministic local category precedence

**Files:**

- Create: `apps/api/spend_memory/enrichment/categories.py`
- Modify: `apps/api/spend_memory/enrichment/repository.py`
- Test: `apps/api/tests/test_category_resolution.py`

**Interfaces:**

- Consumes: `MerchantMatch`, categories, merchant assignments, and transaction overrides from Tasks 1 and 2.
- Produces: `CategoryResolver.resolve(transaction, merchant_match) -> CategoryDecision` for Tasks 4, 7, and 9.

- [ ] **Step 1: Write failing category-precedence tests**

```python
def test_transaction_override_wins_over_confirmed_merchant_category(repository: EnrichmentRepository) -> None:
    merchant = repository.create_merchant("MetroMart")
    groceries = repository.create_category("Groceries")
    gifts = repository.create_category("Gifts")
    repository.assign_merchant_category(merchant.merchant_id, groceries.category_id)
    transaction = _transaction()
    repository.set_transaction_category_override(transaction.raw_transaction_id, gifts.category_id)

    result = CategoryResolver(repository).resolve(transaction, _confirmed_match(merchant))

    assert result == CategoryDecision(gifts.category_id, "Gifts", "transaction_override")


def test_suggested_merchant_does_not_assign_a_category(repository: EnrichmentRepository) -> None:
    merchant = repository.create_merchant("MetroMart")
    category = repository.create_category("Groceries")
    repository.assign_merchant_category(merchant.merchant_id, category.category_id)

    assert CategoryResolver(repository).resolve(_transaction(), _suggested_match(merchant)) == CategoryDecision(None, "Uncategorized", "none")
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `uv run pytest apps/api/tests/test_category_resolution.py -v`

Expected: FAIL because `CategoryResolver` does not exist.

- [ ] **Step 3: Implement the three-step decision table**

```python
class CategoryResolver:
    def __init__(self, repository: EnrichmentRepository) -> None:
        self.repository = repository

    def resolve(self, transaction: TrustedTransaction, merchant_match: MerchantMatch) -> CategoryDecision:
        override = self.repository.find_transaction_category_override(transaction.raw_transaction_id)
        if override is not None:
            return CategoryDecision(override.category_id, override.category_label, "transaction_override")
        if merchant_match.status == "confirmed" and merchant_match.merchant_id is not None:
            category = self.repository.find_merchant_category(merchant_match.merchant_id)
            if category is not None:
                return CategoryDecision(category.category_id, category.category_label, "merchant_assignment")
        return CategoryDecision(None, "Uncategorized", "none")
```

Reject blank category names in the repository. Do not add a classifier, training table, or model-version field in this task because no measured baseline has justified one.

- [ ] **Step 4: Run focused category and storage tests**

Run: `uv run pytest apps/api/tests/test_category_resolution.py apps/api/tests/test_enrichment_repository.py -v`

Expected: PASS.

- [ ] **Step 5: Commit and push**

```bash
git add apps/api/spend_memory/enrichment/categories.py apps/api/spend_memory/enrichment/repository.py apps/api/tests/test_category_resolution.py
git commit -m "categorize confirmed merchants"
git push
```

### Task 4: Publish confirmed enrichment to dbt marts

**Files:**

- Modify: `analytics/models/sources.yml`
- Modify: `analytics/models/marts/mart_transactions.sql`
- Modify: `analytics/models/marts/mart_merchants.sql`
- Modify: `analytics/models/marts/mart_categories.sql`
- Modify: `analytics/models/marts/mart_recurring_groups.sql`
- Modify: `analytics/models/marts/mart_category_summary.sql`
- Modify: `analytics/models/marts/marts.yml`
- Modify: `apps/api/tests/test_analytics_models.py`

**Interfaces:**

- Consumes: main-schema enrichment tables from Task 1 and confirmed annotations from Task 9.
- Produces: enrichment-aware `analytics.mart_transactions`, dimensions, and category summary for all later analytical work.

- [ ] **Step 1: Write failing dbt integration tests**

```python
def test_mart_transactions_exposes_only_confirmed_merchant_and_category(tmp_path: Path) -> None:
    database_path = _build_fixture_database(tmp_path)
    enrichment = EnrichmentRepository(database_path)
    merchant = enrichment.create_merchant("MetroMart")
    groceries = enrichment.create_category("Groceries")
    enrichment.assign_merchant_category(merchant.merchant_id, groceries.category_id)
    transaction_id = _trusted_transaction_id(database_path, "METRO MART")
    enrichment.save_merchant_annotation(transaction_id, _confirmed_match(merchant))
    suggested_id = _trusted_transaction_id(database_path, "METRO-MART")
    enrichment.save_merchant_annotation(suggested_id, _suggested_match(merchant))

    _dbt_build(database_path, "mart_transactions mart_merchants mart_categories")

    with duckdb.connect(str(database_path), read_only=True) as connection:
        rows = connection.execute("select raw_transaction_id, merchant_id, category_id from analytics.mart_transactions where raw_transaction_id in (?, ?) order by raw_transaction_id", [transaction_id, suggested_id]).fetchall()
    assert rows == [(transaction_id, merchant.merchant_id, groceries.category_id), (suggested_id, None, None)]
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `uv run pytest apps/api/tests/test_analytics_models.py::test_mart_transactions_exposes_only_confirmed_merchant_and_category -v`

Expected: FAIL because enrichment tables are not dbt sources and marts still contain placeholder columns.

- [ ] **Step 3: Add dbt sources and confirmed-only joins**

Add `merchants`, `categories`, `merchant_category_assignments`, `transaction_category_overrides`, `transaction_merchant_annotations`, and `recurring_candidates` to `sources.yml` under `schema: main`.

Replace the placeholder fields in `mart_transactions.sql` with confirmed-only joins. The core of the query must be:

```sql
left join {{ source('spend_memory', 'transaction_merchant_annotations') }} as annotation
  on transactions.raw_transaction_id = annotation.raw_transaction_id
  and annotation.resolution_status = 'confirmed'
left join {{ source('spend_memory', 'transaction_category_overrides') }} as override
  on transactions.raw_transaction_id = override.raw_transaction_id
left join {{ source('spend_memory', 'merchant_category_assignments') }} as assignment
  on annotation.merchant_id = assignment.merchant_id
select
  ...,
  annotation.merchant_id,
  coalesce(override.category_id, assignment.category_id) as category_id,
  cast(null as varchar) as recurring_group_id,
  coalesce(annotation.enrichment_version, 'unavailable') as enrichment_version
```

Make `mart_merchants` and `mart_categories` select their real local dimensions. Keep `mart_recurring_groups` empty until Task 9 maps review candidates into that dimension. Keep the existing trusted-mart reconciliation join unchanged.

- [ ] **Step 4: Extend dbt schema tests and run the analytics suite**

Require `merchant_id`, `category_id`, and `enrichment_version` to be nullable in `marts.yml`, while preserving all existing non-null source and money-column tests. Add a category-summary assertion that unconfirmed suggestions remain in `uncategorized`.

Run: `uv run pytest apps/api/tests/test_analytics_models.py -v && SPEND_MEMORY_DUCKDB_PATH=/tmp/spend-memory-m4-check.duckdb uv run dbt parse --project-dir analytics --profiles-dir analytics`

Expected: PASS and dbt parse exits 0.

- [ ] **Step 5: Commit and push**

```bash
git add analytics apps/api/tests/test_analytics_models.py
git commit -m "publish confirmed enrichment"
git push
```

### Task 5: Detect recurring-payment candidates with explainable rules

**Files:**

- Create: `apps/api/spend_memory/enrichment/recurring.py`
- Modify: `apps/api/spend_memory/enrichment/repository.py`
- Test: `apps/api/tests/test_recurring_candidates.py`

**Interfaces:**

- Consumes: ordered debit `TrustedTransaction` rows and confirmed merchant annotations.
- Produces: `RecurringCandidate` records and `detect_recurring_candidates(transactions, matches_by_transaction_id) -> list[RecurringCandidate]` for Task 9.

- [ ] **Step 1: Write failing cadence and evidence tests**

```python
def test_monthly_candidate_explains_dates_amount_range_and_next_window() -> None:
    result = detect_recurring_candidates([
        _transaction("2026-01-02", -2999, "STREAMBOX MONTHLY"),
        _transaction("2026-02-03", -2999, "STREAMBOX MONTHLY"),
        _transaction("2026-03-02", -3099, "STREAMBOX MONTHLY"),
    ], matches_by_transaction_id={})

    assert result[0].cadence == "monthly"
    assert result[0].amount_min_minor == 2999
    assert result[0].amount_max_minor == 3099
    assert result[0].expected_next_start.isoformat() == "2026-03-30"
    assert result[0].expected_next_end.isoformat() == "2026-04-05"


def test_credits_and_irregular_repeats_are_not_recurring_candidates() -> None:
    assert detect_recurring_candidates(_credits_and_irregular_debits(), matches_by_transaction_id={}) == []
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `uv run pytest apps/api/tests/test_recurring_candidates.py -v`

Expected: FAIL because recurring detection does not exist.

- [ ] **Step 3: Implement a small rules-only detector**

Group only debit rows by `(account_identity, merchant_id or normalized_description, currency)`. Require at least three rows. Compare consecutive intervals against these fixed windows:

```python
CADENCES = {
    "weekly": (5, 9),
    "monthly": (26, 35),
    "quarterly": (80, 100),
    "annual": (350, 380),
}

def _amounts_are_consistent(values: list[int]) -> bool:
    return max(values) - min(values) <= max(1, round(max(values) * 0.1))
```

Use `abs(amount_minor)` only for candidate range evidence. Preserve the source direction and never change a transaction. Derive the next window from the final observed date and the accepted interval window. Write candidates with a stable key and `status='candidate'`; refresh replaces generated candidate rows only, never confirmed corrections or source data.

- [ ] **Step 4: Run focused tests**

Run: `uv run pytest apps/api/tests/test_recurring_candidates.py -v`

Expected: PASS, including weekly, monthly, quarterly, annual, amount-tolerance, credit, and irregular-repeat cases.

- [ ] **Step 5: Commit and push**

```bash
git add apps/api/spend_memory/enrichment/recurring.py apps/api/spend_memory/enrichment/repository.py apps/api/tests/test_recurring_candidates.py
git commit -m "find recurring payments"
git push
```

### Task 6: Produce review-only duplicate and unusual-spend candidates

**Files:**

- Create: `apps/api/spend_memory/enrichment/review.py`
- Modify: `apps/api/spend_memory/enrichment/repository.py`
- Test: `apps/api/tests/test_review_candidates.py`

**Interfaces:**

- Consumes: `TrustedTransaction` rows and resolved merchant IDs where confirmed.
- Produces: `find_duplicate_candidates(transactions, matches_by_transaction_id)` and `find_unusual_spend_candidates(transactions, matches_by_transaction_id)` for Task 9.

- [ ] **Step 1: Write failing review-candidate tests**

```python
def test_same_day_same_debit_is_a_duplicate_review_candidate() -> None:
    candidates = find_duplicate_candidates([
        _transaction("2026-03-12", -12500, "METRO MART", raw_id=UUID(int=1)),
        _transaction("2026-03-12", -12500, "MetroMart POS", raw_id=UUID(int=2)),
    ], matches_by_transaction_id={})
    assert candidates[0].raw_transaction_ids == (UUID(int=1), UUID(int=2))
    assert candidates[0].confidence == 1.0


def test_refund_reversal_and_legitimate_repeat_are_not_called_duplicates() -> None:
    assert find_duplicate_candidates(_refund_reversal_and_repeat_rows(), matches_by_transaction_id={}) == []


def test_unusual_candidate_needs_history_and_uses_median_absolute_deviation() -> None:
    candidates = find_unusual_spend_candidates(_five_small_purchases_then_one_large_purchase(), matches_by_transaction_id={})
    assert [candidate.raw_transaction_id for candidate in candidates] == [UUID(int=6)]
    assert find_unusual_spend_candidates(_only_two_purchases(), matches_by_transaction_id={}) == []
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `uv run pytest apps/api/tests/test_review_candidates.py -v`

Expected: FAIL because review rules do not exist.

- [ ] **Step 3: Implement conservative duplicate evidence**

Only compare rows in the same account, currency, direction, and a one-day window. Use confirmed merchant ID when both are available, otherwise equal normalized descriptions. Require equal absolute amounts. A pair earns `1.0` only when all evidence matches. Exclude opposite directions so refunds and reversals cannot become duplicates. Keep raw ID pairs sorted before persistence.

- [ ] **Step 4: Implement robust personal-history unusual-spend evidence**

For debit rows grouped by account, currency, and confirmed merchant ID or normalized descriptor, require at least five earlier values. Calculate:

```python
median_amount = statistics.median(history)
mad = statistics.median(abs(value - median_amount) for value in history)
is_unusual = mad > 0 and amount > median_amount + 4 * mad
```

Store the median, MAD, observed amount, group key, and sample size as evidence. Return `[]` for zero MAD or thin history instead of inventing a score. Call all output `candidate` in code and documentation. Do not use the term fraud.

- [ ] **Step 5: Run focused review tests**

Run: `uv run pytest apps/api/tests/test_review_candidates.py -v`

Expected: PASS.

- [ ] **Step 6: Commit and push**

```bash
git add apps/api/spend_memory/enrichment/review.py apps/api/spend_memory/enrichment/repository.py apps/api/tests/test_review_candidates.py
git commit -m "flag review candidates"
git push
```

### Task 7: Build local structured and lexical transaction search

**Files:**

- Create: `apps/api/spend_memory/enrichment/search.py`
- Test: `apps/api/tests/test_transaction_search.py`

**Interfaces:**

- Consumes: `TrustedTransaction` rows, `CategoryDecision`, and confirmed merchant names.
- Produces: `parse_search_query(query: str) -> SearchQuery` and `search_transactions(rows, query) -> list[SearchResult]` for Milestone 5.

- [ ] **Step 1: Write failing grammar and ranking tests**

```python
def test_search_combines_structured_filters_and_free_text() -> None:
    query = parse_search_query('currency:AED direction:debit after:2026-01-01 metro')
    results = search_transactions(_search_rows(), query)

    assert [result.transaction.description for result in results] == ["METRO MART", "MetroMart POS"]


def test_search_rejects_unknown_filter_and_invalid_amount_range() -> None:
    with pytest.raises(SearchQueryError, match="unknown_filter"):
        parse_search_query("planet:mars")
    with pytest.raises(SearchQueryError, match="invalid_amount_range"):
        parse_search_query("amount:50..10")
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `uv run pytest apps/api/tests/test_transaction_search.py -v`

Expected: FAIL because query parsing and search do not exist.

- [ ] **Step 3: Implement the small documented grammar**

Support these exact `key:value` filters: `after`, `before`, `currency`, `direction`, `merchant`, `category`, `amount`, and `state`. `amount` accepts a closed integer-minor-unit range such as `amount:100..5000`. Unprefixed tokens form a free-text phrase. Reject duplicate scalar filters, unknown keys, invalid ISO dates, invalid directions, and invalid ranges with `SearchQueryError` codes.

Use the shared `SearchQuery` record rather than defining another query shape:

```python
from spend_memory.enrichment.models import SearchQuery
```

- [ ] **Step 4: Implement deterministic lexical ranking**

Filter first. For remaining rows, normalize the raw descriptor and compare token sets. Score exact normalized-description equality as `1.0`, an exact token-set match as `0.9`, and Jaccard token overlap otherwise. Sort by descending score, then newest transaction date, then raw transaction UUID text. Return no result for an empty free-text query unless at least one structured filter is present.

- [ ] **Step 5: Add the 50-query synthetic evaluation and run tests**

Add exactly 50 synthetic queries covering all filters, descriptor variants, multi-currency isolation, empty results, and invalid grammar. Assert expected first result IDs and calculate `MRR@10` for the lexical baseline. Record the number in a test assertion so future semantic work has a comparison point. Do not add embeddings, a model dependency, or semantic retrieval.

Run: `uv run pytest apps/api/tests/test_transaction_search.py -v`

Expected: PASS.

- [ ] **Step 6: Commit and push**

```bash
git add apps/api/spend_memory/enrichment/search.py apps/api/tests/test_transaction_search.py
git commit -m "search local transactions"
git push
```

### Task 8: Generate exact period-change explanations

**Files:**

- Create: `apps/api/spend_memory/enrichment/periods.py`
- Test: `apps/api/tests/test_period_explanations.py`

**Interfaces:**

- Consumes: trusted transaction rows, confirmed category and merchant labels, and recurring-candidate membership.
- Produces: `explain_period_change(before, after) -> PeriodExplanation` for Milestone 5.

- [ ] **Step 1: Write failing exact-reconciliation tests**

```python
def test_period_explanation_contributions_and_remainder_sum_exactly() -> None:
    explanation = explain_period_change(
        before=_period_rows("2026-01", metro=-1000, streambox=-2999),
        after=_period_rows("2026-02", metro=-1500, streambox=-2999, raw=-200),
    )

    assert explanation.before_net_amount_minor == -3999
    assert explanation.after_net_amount_minor == -4699
    assert explanation.difference_net_amount_minor == -700
    assert explanation.contribution_total_minor + explanation.remainder_minor == -700
    assert "700 minor units more out" in explanation.text


def test_period_explanation_never_crosses_currency_or_uses_float_money() -> None:
    with pytest.raises(PeriodExplanationError, match="mixed_currency"):
        explain_period_change(_aed_rows(), _pkr_rows())
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `uv run pytest apps/api/tests/test_period_explanations.py -v`

Expected: FAIL because the period service does not exist.

- [ ] **Step 3: Implement deterministic decomposition and template text**

Calculate all totals with `sum(row.amount_minor if row.direction == 'credit' else -row.amount_minor for row in rows)` only if the input records carry positive `amount_minor`; adapt the expression to the existing `net_amount_minor` query result if it is already supplied. Keep all values `int` and assert this before returning.

Group changes in this order: recurring group, confirmed merchant, confirmed category, then normalized descriptor. Select the largest absolute contributors without double-counting: once a transaction is allocated to an earlier group, remove it from later groups. Define the remainder exactly as:

```python
remainder_minor = difference_net_amount_minor - sum(contribution.amount_minor for contribution in contributions)
assert sum(contribution.amount_minor for contribution in contributions) + remainder_minor == difference_net_amount_minor
```

Render fixed language such as `"Spending was 700 minor units more out than the previous period. MetroMart accounted for 500 minor units."` Use raw or normalized descriptors when merchant and category remain unconfirmed. Reject empty periods, mixed currencies, and mismatched accounts with named `PeriodExplanationError` codes.

- [ ] **Step 4: Run focused period tests**

Run: `uv run pytest apps/api/tests/test_period_explanations.py -v`

Expected: PASS, including recurring, merchant, category, raw-descriptor, credit, exact-remainder, mixed-currency, and mixed-account cases.

- [ ] **Step 5: Commit and push**

```bash
git add apps/api/spend_memory/enrichment/periods.py apps/api/tests/test_period_explanations.py
git commit -m "explain period changes"
git push
```

### Task 9: Orchestrate a local refresh and verify the full path

**Files:**

- Create: `apps/api/spend_memory/enrichment/service.py`
- Modify: `apps/api/spend_memory/enrichment/repository.py`
- Modify: `analytics/models/marts/mart_recurring_groups.sql`
- Modify: `analytics/models/marts/mart_transactions.sql`
- Modify: `analytics/models/marts/marts.yml`
- Create: `apps/api/tests/test_enrichment_service.py`
- Create: `docs/architecture.md`

**Interfaces:**

- Consumes: all Task 1 through 8 components and a built `analytics.mart_transactions` table.
- Produces: `EnrichmentService.refresh() -> RefreshResult`, which Milestone 5 can call behind a future API route.

- [ ] **Step 1: Write the failing end-to-end refresh test**

```python
def test_refresh_reads_only_reconciled_mart_rows_and_persists_reviewable_outputs(tmp_path: Path) -> None:
    database_path = _build_fixture_database(tmp_path)
    _dbt_build(database_path, "mart_transactions")
    repository = EnrichmentRepository(database_path)
    merchant = repository.create_merchant("MetroMart")
    repository.confirm_alias("METRO MART", merchant.merchant_id)

    result = EnrichmentService(repository).refresh()

    assert result.transaction_count == 864
    assert result.confirmed_merchant_count > 0
    assert result.recurring_candidate_count >= 2
    with duckdb.connect(str(database_path), read_only=True) as connection:
        assert connection.execute("select count(*) from transaction_merchant_annotations").fetchone()[0] == 864
        assert connection.execute("select count(*) from raw_transactions").fetchone()[0] == 864
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `uv run pytest apps/api/tests/test_enrichment_service.py -v`

Expected: FAIL because `EnrichmentService` does not exist.

- [ ] **Step 3: Implement one explicit refresh method**

```python
@dataclass(frozen=True)
class RefreshResult:
    transaction_count: int
    confirmed_merchant_count: int
    suggested_merchant_count: int
    unresolved_merchant_count: int
    recurring_candidate_count: int
    duplicate_candidate_count: int
    unusual_spend_candidate_count: int


class EnrichmentService:
    def __init__(self, repository: EnrichmentRepository) -> None:
        self.repository = repository

    def refresh(self) -> RefreshResult:
        transactions = self.repository.list_trusted_transactions()
        matches = {transaction.raw_transaction_id: self.merchant_resolver.resolve(transaction) for transaction in transactions}
        self.repository.replace_merchant_annotations(matches)
        self.repository.record_confirmed_currencies(transactions, matches)
        self.repository.replace_recurring_candidates(detect_recurring_candidates(transactions, matches))
        self.repository.replace_duplicate_candidates(find_duplicate_candidates(transactions, matches))
        self.repository.replace_unusual_spend_candidates(find_unusual_spend_candidates(transactions, matches))
        return self.repository.summarize_refresh(matches)
```

Add these methods to `EnrichmentRepository` in this task:

```python
def list_trusted_transactions(self) -> list[TrustedTransaction]: ...
def replace_merchant_annotations(self, matches: dict[UUID, MerchantMatch]) -> None: ...
def record_confirmed_currencies(self, transactions: list[TrustedTransaction], matches: dict[UUID, MerchantMatch]) -> None: ...
def replace_recurring_candidates(self, candidates: list[RecurringCandidate]) -> None: ...
def replace_duplicate_candidates(self, candidates: list[DuplicateCandidate]) -> None: ...
def replace_unusual_spend_candidates(self, candidates: list[UnusualSpendCandidate]) -> None: ...
def summarize_refresh(self, matches: dict[UUID, MerchantMatch]) -> RefreshResult: ...
```

`list_trusted_transactions()` must query `analytics.mart_transactions` and fail with `trusted_mart_unavailable` if the mart is missing. It must not fall back to raw transactions. Replacement methods delete and insert only generated candidate records within one writer-locked transaction and must never delete corrections, aliases, categories, source rows, or documents.

Map recurring candidates into `mart_recurring_groups.sql` as a review-candidate dimension only. Keep `mart_transactions.recurring_group_id` nullable because a candidate is not a confirmed fact.

- [ ] **Step 4: Document the boundary and run the full verification suite**

Document these facts in `docs/architecture.md`:

```markdown
## Enrichment

Enrichment reads reconciled analytics marts and writes local annotations. Confirmed aliases and category assignments can affect analytical labels. Suggestions, recurring candidates, possible duplicates, and unusual-spend candidates remain review signals and never change a transaction or a total. The period explanation engine uses integer minor units and fixed templates. Milestone 5 will expose these local services through API routes.
```

Run:

```bash
make test
make lint
uv run pytest apps/api/tests/test_analytics_models.py apps/api/tests/test_enrichment_service.py -v
```

Expected: every command exits 0. Build analytics once against a generated local fixture as the final data-lineage check:

```bash
SPEND_MEMORY_DUCKDB_PATH=/tmp/spend-memory-m4-final.duckdb uv run dbt build --project-dir analytics --profiles-dir analytics
```

Expected: dbt exits 0 after the fixture database has been created by the test helper or an equivalent local synthetic setup.

- [ ] **Step 5: Run Ponytail and review the branch**

Run the Ponytail audit on the complete branch. Remove any speculative helper, dependency, or persistence column it identifies unless a test above depends on it. Then run the full verification commands again.

- [ ] **Step 6: Commit and push**

```bash
git add apps/api/spend_memory/enrichment/service.py apps/api/spend_memory/enrichment/repository.py analytics/models/marts apps/api/tests/test_enrichment_service.py docs/architecture.md
git commit -m "refresh local enrichment"
git push
```

## Self-review

### Spec coverage

- Merchant normalization, exact aliases, character n-gram TF-IDF retrieval, local ranking, unresolved results, merchant-level evaluation, and calibration are covered by Task 2.
- Editable categories, deterministic precedence, low-confidence fallback, and the evidence gate that prevents premature classifiers are covered by Task 3.
- Explainable recurring candidates across the four required cadences are covered by Task 5.
- Conservative duplicate and robust personal-history unusual-spend candidates, with no fraud claims, are covered by Task 6.
- Structured filters, lexical retrieval, documented grammar, and the 50-query local evaluation are covered by Task 7. Semantic retrieval is deliberately not added because it has not passed the required evidence gate.
- Exact arithmetic, contribution reconciliation, template language, and the Task 15 API-route deferral to Milestone 5 are covered by Task 8.
- Local-only persistence, reconciled-mart lineage, analytics exposure, refresh orchestration, docs, CI, and the Ponytail audit are covered by Tasks 1, 4, and 9.

### Placeholder scan

The plan contains no undefined implementation steps, no deferred code markers, and no generic test instructions. Every task states its files, concrete interfaces, test command, expected result, and commit command.

### Type consistency

All downstream components consume `TrustedTransaction`, `MerchantMatch`, and `CategoryDecision` defined before Task 1. Candidate-producing functions are consumed only by `EnrichmentService.refresh()` in Task 9. The period service remains pure and is not coupled to a future FastAPI route.
