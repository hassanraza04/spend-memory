# Task 8 report: show result summaries

## Result

The activity ledger now renders a quiet, accessible `Result summary` region after its table and before the trusted-entry count. It receives the already-loaded `WorkspaceLens` from the page and reuses `LensSummary` unchanged for each currency. The summary says it covers all matching entries. An empty result retains the existing empty message and adds `0 matching entries.` without a money value.

## RED and GREEN evidence

### RED

Added the focused ledger tests before production changes. The project-local Vitest run reported two expected failures and three existing passes:

```text
Unable to find an accessible element with the role "region" and name "Result summary"
Test Files 1 failed
Tests 2 failed | 3 passed
```

The supplied page test also required this missing region for a search response whose server lens differed from the one rendered row.

### GREEN

```text
node_modules/.bin/vitest run src/app/page.test.tsx src/components/transaction-ledger.test.tsx --reporter=dot
Test Files 2 passed
Tests 20 passed

node_modules/.bin/eslint .
passed

node_modules/.bin/next build
compiled, type-checked, and generated static pages

git diff --check
passed
```

The focused browser test also passed after a real UI search:

```text
node_modules/.bin/playwright test tests/e2e/demo.spec.ts --grep "complete API-derived"
1 passed
```

## Source-of-totals proof

- `Page` already stores the search response as `{ lens: result.lens, trend: [] }` and the normal response as `api.getLens(scope)`.
- `page.tsx` passes that loaded `WorkspaceLens` directly to `TransactionLedger`.
- `TransactionLedger` passes only `lens.lens` to the existing `LensSummary` component.
- `LensSummary` remains the only renderer of sent, received, net, and count values. It uses the existing `formatMoney` formatter.
- The page test supplies one AED 12.00 visible row but a two-currency API lens with AED 12.34 sent, AED 5.67 received, AED -6.67 net, two entries, and USD $8.90. The rendered summary asserts those lens values. There is no client money arithmetic.

## Tests added or retained

- Page test: search lens values render even when they differ from the visible row.
- Ledger test: semantic region is after the table and before the entry count, names all matching entries, and renders AED and USD flows.
- Ledger test: an empty page says zero matching entries and contains no fabricated currency or decimal money value.
- E2E test: a person searches demo activity through the existing filter UI and sees the result-summary region. It does not assert static fixture totals or bypass the UI flow.

## Exact staged paths and commit

- `.superpowers/sdd/task-8-report.md`
- `apps/web/src/app/globals.css`
- `apps/web/src/app/page.test.tsx`
- `apps/web/src/app/page.tsx`
- `apps/web/src/components/transaction-ledger.test.tsx`
- `apps/web/src/components/transaction-ledger.tsx`
- `apps/web/tests/e2e/demo.spec.ts`

Commit subject: `show result summaries`.

## Self-review and concerns

The change adds no route, data store, formatter, dependency, money calculation, or API call. It reuses the loaded API lens and existing summary cards. The zero-result branch intentionally reads only the API page total and does not infer amounts.

The requested `pnpm` wrapper does not produce a conclusive direct run in this terminal, and the unchanged Playwright web-server command exits 3 through that wrapper. Equivalent project-local binaries passed the unit, lint, and build checks. The focused E2E test passed with the same local API and production web servers started manually. The full existing demo spec still has a non-Task-8 failure: its first test expects January after `resetDemo(page, "")`, but this environment routes to the available April scope.

## Pagination review repair

Reviewer feedback identified that search pages can have no visible rows while their API lens remains non-empty. Page metadata is therefore not authoritative for the result summary.

- RED: new page and ledger tests supplied `page.items: []`, `page.total: 0`, and an AED API lens with two matching entries. Both failed because the region rendered `0 matching entries.` instead of the AED lens total.
- GREEN: `TransactionLedger` now uses `lens.lens.length` to select `LensSummary`; it shows `0 matching entries.` only when the API lens is empty.
- Fresh verification: focused page and ledger tests passed, 22 tests total; ESLint, production build, and `git diff --check` passed.
