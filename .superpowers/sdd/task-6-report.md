# Task 6 report: grouped activity evidence

## Status

Task 6 is complete on `feature/focused-product-repair`.

The implementation adds the compatibility-preserving `GET /api/v1/people-places` resource. It also adds shared entity scope fields. Existing `/merchants`, `/categories`, `/recurring`, and `/review` response bodies keep their prior shapes.

## TDD record

### RED 1: existing merchant boundary

Command:

```bash
UV_CACHE_DIR=/private/tmp/spend-memory-task6-uv uv run pytest apps/api/tests/test_api_entities.py -q
```

Observed result before implementation: `1 failed, 3 passed`. The pending boundary test expected one January merchant. The endpoint returned two rows because the February 1 row was not excluded.

### GREEN 1: half-open merchant dates

The same command then reported `4 passed`. `MerchantEvidence` now carries its trusted transaction date. The public merchant response does not expose that added internal field.

### RED 2: grouped API resource

The grouped endpoint tests were added before the endpoint. The focused command reported `2 failed, 4 passed`. Both new tests received `404 Not Found` for `/api/v1/people-places`.

### RED 3: assigned counterparty identity

The person test first received a generated label key instead of the expected assigned counterparty UUID key. The focused command reported `1 failed, 7 passed`. The implementation now reads local counterparty assignments and returns `counterparty:<uuid>`.

### RED 4: typed web client

Command:

```bash
apps/web/node_modules/.bin/vitest run apps/web/src/lib/api.test.ts
```

Observed result with the client method removed: `1 failed, 3 passed`. The failure was `listPeoplePlaces is not a function`.

### Final GREEN

Commands and results:

```bash
UV_CACHE_DIR=/private/tmp/spend-memory-task6-uv uv run pytest apps/api/tests/test_api_entities.py -q
# 8 passed

pnpm --dir apps/web exec vitest run src/lib/api.test.ts
# 4 passed

UV_CACHE_DIR=/private/tmp/spend-memory-task6-uv uv run ruff check apps/api/spend_memory/api/contracts.py apps/api/spend_memory/enrichment/repository.py apps/api/spend_memory/api/routes/entities.py apps/api/tests/test_api_entities.py
# All checks passed

cd apps/web && node_modules/.bin/eslint src/lib/api.ts src/lib/api.test.ts
# passed with no findings

git diff --check
# passed with no findings
```

The full API suite was also started. It reached `86 passed` with no failures before it was stopped after 208 seconds to complete the requested handoff.

## External contract

`GET /api/v1/people-places` accepts `limit`, `offset`, `sort`, `order`, and `status`. It also accepts the shared optional `after`, `before`, `account`, `currency`, `direction`, and `query` scope fields.

Dates use `[after, before)` semantics. Text search uses the existing trusted transaction search behavior.

The response is a normal page:

```json
{
  "items": [],
  "limit": 50,
  "offset": 0,
  "total": 0
}
```

Each non-empty item contains `key`, `label`, `kind`, `status`, `transactionCount`, `lastActivityDate`, `flows`, and `recentTransactionIds`.

Confirmed merchants use `merchant:<uuid>` and `kind: "place"`. Assigned counterparties use `counterparty:<uuid>` and `kind: "person"`. Unresolved descriptions are grouped only with other rows that have the same normalized internal description. Their public label is always `Unresolved statement label`. Their key uses a transaction UUID and does not expose the description.

Flows use `summarize_lens`. Money remains exact integer minor units. Currencies sort deterministically. Recent transaction IDs sort by date and ID, newest first. Groups sort by label and key before pagination.

An empty trusted result returns an empty page. An unavailable trusted mart returns the established `503 trusted_records_unavailable` response. No cards are fabricated.

Legacy entity behavior remains compatible:

- `/merchants` keeps its response fields and now filters evidence with inclusive `after` and exclusive `before` dates. Account, currency, direction, and query scopes filter by trusted transaction ID.
- `/categories` keeps its response fields and its existing currency-only behavior. Combined scopes rebuild exact category lenses from the trusted scoped rows.
- `/recurring` and `/review` keep their response fields. With a scope, an item appears only when every member transaction ID is in the trusted scoped set.
- With no scope, all four legacy resources keep whole-record behavior.

The web client adds the `PeoplePlace` type and `ApiClient.listPeoplePlaces(scope)`.

## Implementation and self-review

The route reuses `EnrichmentRepository.list_search_rows()`, `search_transactions` through `filtered_rows`, and `summarize_lens`. Grouping is one local O(n) pass over the scoped rows.

The repository change adds transaction dates to merchant evidence. It also adds one small local assignment reader so public person keys use real counterparty UUIDs.

No cache, service layer, external call, dependency, database schema, ML behavior, or endpoint family was added. No raw statement descriptor field is present in the grouped public contract.

The intentional Task 8 changes in `apps/web/src/app/page.test.tsx` and `apps/web/tests/e2e/demo.spec.ts` were not edited or staged.

## Exact staged paths and commit

The intended staged paths are:

```text
.superpowers/sdd/task-6-report.md
apps/api/spend_memory/api/contracts.py
apps/api/spend_memory/api/routes/entities.py
apps/api/spend_memory/enrichment/repository.py
apps/api/tests/test_api_entities.py
apps/web/src/lib/api.test.ts
apps/web/src/lib/api.ts
```

Branch: `feature/focused-product-repair`

Commit subject: `group activity evidence`

## Concerns

The full web TypeScript check currently fails only in the intentional unstaged Task 8 page test scaffolding. Its six errors say that `toHaveTextContent` is missing from the assertion type. Task 6 web files pass ESLint and their focused Vitest suite.

The API focused suite emits existing SWIG and Starlette deprecation warnings. No Task 6 test emits a functional warning or failure.

`recentTransactionIds` includes all transactions in each scoped group because the brief does not set a maximum. The local personal-statement scope bounds this deliberate choice.
