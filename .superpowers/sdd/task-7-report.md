# Task 7 report: comparison defaults

## Result

The compare screen now uses the existing `GET /workspace-context` response as
normal page data. It adds no comparison-options endpoint, store, dependency,
cache, client money calculation, or custom picker.

When a compare URL has activity, a current period, and neither `account` nor
`currency`, the page chooses the first ordered context entry with a currency.
For the page test that pair is `Daily` and `AED`. The URL becomes:

```text
?view=compare&after=2026-04-01&before=2026-05-01&account=Daily&currency=AED
```

That current period is 30 days long. Its immediately preceding equal-length
period is March 2 through April 1, so the existing endpoint is called with:

```text
before_start=2026-03-02
before_end=2026-04-01
after_start=2026-04-01
after_end=2026-05-01
account=Daily
currency=AED
```

The automatic default uses one `history.replaceState` call. Any explicit
account or currency remains unchanged, including an invalid or partial pair.
Only a pair present in workspace context can reach the comparison endpoint.
Changing the native account select chooses that account's first ordered
currency. Changing the native currency select keeps the account and updates
the currency. Both changes use the existing workspace scope update path.

## Empty and incomplete states

- No local workspace says: `There is no local activity to compare yet.`
- A `comparison_unavailable` response from the existing endpoint says:
  `An earlier matching period is needed before this month can be compared.`
- A missing or invalid context pair asks the person to choose a valid account
  and currency from available local activity.
- A valid request shows a loading status, a local API error, or the exact
  server response. It never leaves an inactive blank screen.

## Demo integration

The real reset-demo integration compares calendar March with calendar April
for `AED-SYNTH-001` and `AED`. This is separate from the page's equal-length
range construction. The existing server returns an exact net difference of
`-36243` minor units and these three contributions:

- `Quick Cart`: `-26920`
- `nova bazaar`: `-17800`
- `transfer received`: `12500`

The exact server explanation is:

```text
Net activity was 36243 minor units lower than the previous period. Quick Cart accounted for 26920 minor units. nova bazaar accounted for 17800 minor units. transfer received accounted for 12500 minor units. Other activity accounted for 4023 minor units.
```

## TDD evidence

### RED

The page test started at the dated April compare URL without a pair. It failed
because the page did not request workspace context, did not write `Daily/AED`
to the URL, and did not request a comparison.

The component test run reported three failures and two passes. It could not
find the native account options, the no-workspace message, or the
missing-previous-period message.

The reset-demo API test reached the existing deterministic endpoint on its
first implementation-independent run. My first hand-calculated sentence was
wrong, and the assertion exposed the actual exact result shown above. After
correcting the expected fixture output, the test passed without API production
changes. This is expected because Task 5 already added the required history.

Reviewer correction RED: the default page test changed the workspace's first
date to March 15 while retaining valid March and April activity. The current
period still required the March 2 through April 1 request, but the client
suppressed it because March 15 was later than March 2. The test failed without
the server explanation. A second page test returned the real
`comparison_unavailable` API error and failed because the page showed only the
generic comparison error.

Reviewer correction GREEN: the client now validates only the dates and the
context-owned pair, then lets the comparison endpoint decide row
availability. March 15 history requests the exact March 2 through April 1
range. `comparison_unavailable` selects the existing earlier-period guidance,
while other API errors retain their local message.

### GREEN

```text
node_modules/.bin/vitest run src/app/page.test.tsx src/components/comparison-view.test.tsx -t '^(?!.*renders a search result summary)'
19 passed, 1 skipped

UV_CACHE_DIR=/private/tmp/spend-memory-task7-uv uv run pytest apps/api/tests/test_api_comparisons.py -q
3 passed

node_modules/.bin/eslint src/app/page.tsx src/app/page.test.tsx src/components/comparison-view.tsx src/components/comparison-view.test.tsx
passed

UV_CACHE_DIR=/private/tmp/spend-memory-task7-uv uv run ruff check apps/api/tests/test_api_comparisons.py
All checks passed

node_modules/.bin/next build
passed

git diff --check
passed
```

The unfiltered web command has 19 passing tests and one intentional failure:
the existing unstaged Task 8 `Result summary` page scaffold. The requested
`pnpm` wrapper could not be used because the local `pnpm` process hung even for
`pnpm --version`. The checked-in local Vitest and Next binaries completed
normally and were used for equivalent verification.

## Ponytail and self-review

The implementation reuses `WorkspaceContext`, `WorkspaceState`, the existing
scope mutation, the current period, native HTML selects, and the existing
comparison API. The only new page state is the already-fetched context value.
No route, global store, date package, calculation layer, abstraction, or CSS
was added.

The comparison request is gated in one helper by valid dates and a
context-owned pair. The existing endpoint owns row-availability decisions.
Server-returned money and explanation fields remain untouched. Explicit URL
filters are read but never normalized or replaced.

## Staged scope and commit

Task 7 stages only:

- `.superpowers/sdd/task-7-report.md`
- `apps/api/tests/test_api_comparisons.py`
- the Task 7 comparison-default hunk in `apps/web/src/app/page.test.tsx`
- `apps/web/src/app/page.tsx`
- `apps/web/src/components/comparison-view.test.tsx`
- `apps/web/src/components/comparison-view.tsx`

Commit subject: `improve comparison defaults`

The Task 8 result-summary hunk in `apps/web/src/app/page.test.tsx` and the Task
8 hunk in `apps/web/tests/e2e/demo.spec.ts` remain unstaged and unchanged.

## Concerns

No known correctness concern remains. Pair-specific row availability stays
with the deterministic comparison endpoint, so the workspace-wide first date
cannot reject a valid partial preceding period.
