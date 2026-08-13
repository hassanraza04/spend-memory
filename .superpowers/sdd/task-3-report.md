# Task 3 report: workspace context

## Result

Added `GET /api/v1/workspace-context` and the matching typed web client method.
The route returns date bounds, the latest populated calendar month, and ordered
account/currency choices from the local trusted transaction mart. It returns an
empty context when that mart is unavailable. It does not return money totals.

## TDD evidence

### RED

Added focused API route tests and a web API-client test before implementation.

- API: the new endpoint was absent, so the populated and empty context cases
  failed as missing route behavior.
- Web: `ApiClient#getWorkspaceContext` failed with `TypeError: ... is not a
  function`.

### GREEN

Implemented the smallest route, response contracts, repository read method,
and client method needed by those tests.

- `UV_CACHE_DIR=/private/tmp/spend-memory-uv-cache uv run pytest apps/api/tests/test_api_transactions.py -q`
  passed: 8 tests.
- `pnpm --dir apps/web exec vitest run src/lib/api.test.ts` passed: 3 tests.

## Files changed

- `apps/api/spend_memory/api/contracts.py`
- `apps/api/spend_memory/enrichment/repository.py`
- `apps/api/spend_memory/api/routes/transactions.py`
- `apps/api/tests/test_api_transactions.py`
- `apps/web/src/lib/api.ts`
- `apps/web/src/lib/api.test.ts`

## Verification

- Focused API tests: pass, 8 tests.
- Focused client tests: pass, 3 tests.
- `pnpm --dir apps/web build`: passed.

The build emitted existing environment warnings about stale
`baseline-browser-mapping` data and multiple workspace lockfiles. Neither
affected compilation or this change.

## Ponytail review and self-review

The change stays inside the existing transaction route and repository. It uses
two SQL reads against `analytics.mart_transactions`, no cache, no service, no
new dependency, and no monetary calculation. Results are ordered by account
and currency. The latest month is derived from the latest trusted transaction
date, with the exclusive end set to the first day of the next month.

## Concerns

None. Task 6 and Task 8 dirty test files were left untouched and will not be
staged.

## Reviewer follow-up

Added a route integration test that builds a local `analytics.mart_transactions`
table with dates, accounts, and currencies inserted out of order. It invokes
`/api/v1/workspace-context` without a repository override and asserts the
exact date bounds, latest calendar-month range, and ordered account/currency
pairs. The strengthened web test now asserts the returned `WorkspaceContext`
payload as well as the URL.

These tests were written after the production implementation existed, so both
passed on their first run. There was no honest red failure to create without
removing working production code.

- New integration test: passed, 1 test.
- Full affected API file: passed, 9 tests.
- Focused web API-client tests: passed, 3 tests.
