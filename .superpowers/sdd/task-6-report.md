# Task 6 report

## Changes

- Added the current-scope monthly overview, with display-only currency summaries, one server-provided activity trend, and a comparison link.
- Added a semantic transaction ledger with search, direct filters, progressive date, amount, merchant, category, counterparty, and review filters, sorting, URL-backed selection, compact column presets, and keyboard row inspection.
- Added source evidence inspection with Escape-to-close behavior.
- Added explicit local counterparty grouping. People can choose multiple trusted rows, create a label, review server-returned currency-separated totals, and separately confirm an exact alias.
- Added typed API client calls for transactions, search, workspace lens, and counterparty actions. No browser financial arithmetic or currency conversion was added.
- Preserved Personal Record and Night Desk styling with compact editorial tables and narrow-screen layout rules.

## TDD evidence

- The initial component suite failed because the requested components did not exist.
- The URL-state test failed before `mergeWorkspaceState` was added.
- The multi-row grouping test and the fuller filter test each failed before their small UI additions were written.
- The saved counterparty lens display test failed before the editor rendered the API-returned flow.

## Verification

- `pnpm --dir apps/web test` passed: 13 files, 28 tests.
- `pnpm --dir apps/web lint` passed. It emitted only the existing stale `baseline-browser-mapping` advisory.
- `pnpm --dir apps/web exec tsc --noEmit --incremental false` passed. The default incremental command cannot update an existing unwritable `tsconfig.tsbuildinfo` file in this worktree.
- `git diff --check` passed.

## Ponytail review

- Used native tables, form controls, details, local storage, CSS, and the existing local API client. No UI, chart, or state dependency was added.
- The trend is a server-provided timeline rather than a browser-calculated money chart.

## Commit and push

- Commit: `d0de68d build flexible lenses`
- Pushed: `origin/feature/api-interface`
