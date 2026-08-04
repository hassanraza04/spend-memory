# Task 8 report

## Changes

- Added Playwright as the only new development dependency after confirming the runner was absent.
- Added a production-mode local browser harness. It starts the API and web app against one isolated synthetic DuckDB directory per worker.
- Added real browser journeys for the synthetic demo, CSV and scanned-PDF import, duplicate retry, recurring evidence, merchant correction and alias reuse, duplicate evidence, exact comparison, CSV export, and exact local-data deletion.
- Added four checked-in viewport snapshots: wide desktop, laptop, tablet, and narrow mobile.
- Added `make e2e` and the matching CI browser-workflow step. CI installs Chromium before running the local workflows.

## Real issues found and fixed

- First-run actions could begin before the local workspace check completed. The actions stay disabled until that check returns.
- Demo rows did not match the existing reconciliation control, so they never became trusted activity. The demo now uses the reconciled synthetic January statement.
- Mixed DuckDB connection modes could fail active local API reads. The browser-used evidence reads now use the same local connection mode.
- The real merchant-evidence query had an ambiguous join. It now joins the annotation merchant id explicitly.

## TDD evidence

- `pnpm --dir apps/web exec playwright test` first failed because Playwright was not installed.
- The first real demo journey exposed the first-run race and the unreconciled demo data.
- Focused API tests first failed on the DuckDB connection conflict and then on the merchant-evidence join.
- The browser review journey verified the correction is stored locally and is reused by a subsequent real enrichment refresh.

## Verification

- `make lint` passed. The web linter still emits the existing `baseline-browser-mapping` freshness advisory.
- `pnpm --dir apps/web test` passed: 18 files, 51 tests.
- `UV_CACHE_DIR=.uv-cache uv run pytest -q` completed with 242 collected API tests and no recorded pytest failures.
- `pnpm --dir apps/web exec playwright test --reporter=list` passed: 8 of 8 workflows.
- The critical demo, import, export, and deletion workflows passed five repeats: 25 of 25.
- `git diff --check` passed.

## Visual review

I inspected the wide desktop, laptop, tablet, and narrow mobile snapshots. The hierarchy, totals, and controls remain readable. The mobile navigation is intentionally horizontally scrollable, and the ledger uses its existing horizontal scroll behavior rather than compressing financial columns.

## Ponytail review

The work reuses the existing local API, dbt project, synthetic fixtures, browser controls, and CSS. No mock server, test data service, chart package, screenshot service, or extra runtime dependency was added. The only new package is the required free Playwright test runner.
