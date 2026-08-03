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

## Review repair

- Kept the counterparty editor mounted after grouping so the confirmation, returned totals, and exact-alias action remain visible. A failed assignment after label creation now states that the label was created but entries were not grouped.
- Added a one-row unfiltered workspace probe so an empty filtered scope stays in the record while a truly empty workspace still opens first run.
- Restored a URL-selected row into the source panel, defaulted the overview to the current calendar month, and displayed the active date, account, and currency scope.
- Replaced the text-only trend image role with a small accessible SVG that uses server-provided trend values, plus its text key. Grouping checkbox Space presses no longer bubble to the source-row action.
- Added regression coverage for every repair.

Repair verification passed: `pnpm --dir apps/web test` (13 files, 33 tests), `pnpm --dir apps/web lint`, `pnpm --dir apps/web exec tsc --noEmit --incremental false`, and `git diff --check`.

- Repair commit: `eeb2fdb fix lens lifecycle`
