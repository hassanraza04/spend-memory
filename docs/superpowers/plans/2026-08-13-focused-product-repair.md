# Focused Product Repair Implementation Plan

> **For agentic workers:** Required sub-skill: use `subagent-driven-development` or `executing-plans` to complete this plan task by task. Track each task with its checkbox.

**Goal:** Make Spend Memory’s local demo and everyday exploration coherent: valid default dates, meaningful demo evidence, reliable period totals, focused discovery screens, and responsive controls that do not collide.

**Architecture:** Keep monetary calculations in DuckDB-backed API routes. Add a small workspace-context read model that lets the web app choose valid defaults from real records. Seed the synthetic demo as normal imported data plus deterministic enrichment evidence. Keep React as a thin presentation layer and reuse the existing lens for filtered totals.

**Technology:** FastAPI, Pydantic, DuckDB, dbt, Python pytest, Next.js, TypeScript, React Testing Library, Playwright, Docker Compose.

**Constraints:** Data remains local. Demo data remains synthetic. No external services, ML, or client-side monetary aggregation. Periods use `[after, before)` consistently. Keep the existing visual character, but favour readable, native controls over decorative density.

## Baseline and shared test setup

- [ ] **Task 1: Record the repair baseline and add shared boundary fixtures**

  **Files:**
  - Modify: `apps/api/tests/test_api_transactions.py`
  - Modify: `apps/api/tests/test_api_counterparties.py`
  - Modify: `apps/api/tests/test_api_entities.py`
  - Modify: `apps/web/src/app/page.test.tsx`
  - Modify: `apps/web/e2e/demo.spec.ts`

  **Steps:**
  1. Run the relevant API, web unit, and E2E tests before changing code. Save only useful failure output in the PR description, not in the repository.
  2. Add a single seeded transaction at each boundary date. Write failing API tests proving a request for `after=2026-01-01&before=2026-02-01` includes January 1 and excludes February 1.
  3. Add failing UI coverage for a search result summary that receives all money values from the API lens.
  4. Run the narrow test commands and confirm the intended tests fail for the missing behaviour.

  **Commands:**
  ```bash
  UV_CACHE_DIR=.uv-cache uv run pytest apps/api/tests/test_api_transactions.py apps/api/tests/test_api_counterparties.py apps/api/tests/test_api_entities.py -q
  pnpm --dir apps/web test -- --runInBand
  pnpm --dir apps/web exec playwright test e2e/demo.spec.ts
  ```

  **Commit:** No commit. These tests travel with the implementation tasks below.

## Correct record scope and defaults

- [ ] **Task 2: Make every period query use inclusive start and exclusive end**

  **Files:**
  - Modify: `apps/api/spend_memory/enrichment/search.py`
  - Modify: `apps/api/spend_memory/enrichment/repository.py`
  - Modify: `apps/api/spend_memory/api/routes/counterparties.py`
  - Test: files from Task 1

  **Steps:**
  1. Run the Task 1 boundary tests and verify they fail.
  2. Change all query predicates from `transaction_date > after` to `transaction_date >= after`. Retain `transaction_date < before`.
  3. Check both the SQL repository path and in-memory filtering path use the same semantics.
  4. Run the focused API tests, then the full API suite.
  5. Inspect the diff with Ponytail. Keep the change limited to date comparisons and tests.

  **Verification:**
  ```bash
  UV_CACHE_DIR=.uv-cache uv run pytest apps/api/tests -q
  git diff --check
  ```

  **Commit:** `fix date scopes`

- [ ] **Task 3: Expose local workspace context for valid UI defaults**

  **Files:**
  - Modify: `apps/api/spend_memory/api/contracts.py`
  - Modify: `apps/api/spend_memory/enrichment/repository.py`
  - Modify: `apps/api/spend_memory/api/routes/transactions.py` or the existing local-data route module
  - Modify: `apps/web/src/lib/api.ts`
  - Test: `apps/api/tests/test_api_transactions.py`
  - Test: `apps/web/src/lib/api.test.ts` if present, otherwise add a focused test

  **Interface:** Add `GET /workspace-context`, returning only:
  ```json
  {
    "firstTransactionDate": "2026-01-01",
    "lastTransactionDate": "2026-04-30",
    "latestMonthStart": "2026-04-01",
    "latestMonthEnd": "2026-05-01",
    "accounts": [{"account": "Everyday account", "currencies": ["AED"]}]
  }
  ```
  Empty local data returns null dates and an empty account list.

  **Steps:**
  1. Write an API test for ordered dates, latest active calendar month, and account/currency pairs.
  2. Implement a single deterministic repository query/read model. Do not calculate totals here.
  3. Add the route beside existing local read routes and add the typed web client function.
  4. Test empty and populated workspaces.
  5. Run API tests, web typecheck/build, and Ponytail review.

  **Commit:** `add workspace context`

- [ ] **Task 4: Choose defaults from workspace context instead of the device clock**

  **Files:**
  - Modify: `apps/web/src/app/page.tsx`
  - Modify: `apps/web/src/lib/date-range.ts` or the existing date helper
  - Test: `apps/web/src/app/page.test.tsx`
  - Test: `apps/web/e2e/demo.spec.ts`

  **Steps:**
  1. Add a failing page test: after demo data is ready, no explicit query dates shows the context’s latest populated month.
  2. Fetch workspace context during initial load and after import/reset. Preserve explicit user date parameters exactly.
  3. If there is no data, retain the current calm empty state rather than inventing a date range.
  4. Update the URL once defaults are known, with a single `replace` rather than a loop of router writes.
  5. Verify a first-load demo page shows entries without manually changing dates.

  **Commit:** `default to available activity`

## Make the synthetic demo useful

- [ ] **Task 5: Replace the one-month demo with a small, meaningful synthetic record**

  **Files:**
  - Modify: `apps/api/spend_memory/api/dependencies.py`
  - Modify: `apps/api/tests/test_api_local_data.py`
  - Modify: `apps/api/tests/test_api_entities.py`
  - Modify: `apps/api/tests/test_api_transactions.py`

  **Demo contract:** Seed January through April 2026 in AED, with several distinct merchants, a few transfers, an identifiable recurring Streambox payment, one possible duplicate, and at least two intentionally unresolved labels. Include month-to-month variation that gives Compare a concrete explanation.

  **Steps:**
  1. Write failing reset-demo tests that assert four months exist, first-day transactions are visible, and trusted output includes merchant, category, recurring, and review evidence.
  2. Keep the fixture as a compact canonical CSV string. It must contain no real financial data or personal names.
  3. After importing the synthetic raw document, use existing repository methods to create confirmed aliases, merchant categories, and any deterministic annotations needed before the normal refresh runs.
  4. Let normal dbt and enrichment build trusted activity. Do not bypass the product pipeline or manually create mart rows.
  5. Test reset twice to confirm it remains idempotent and does not create duplicate entities.

  **Verification:**
  ```bash
  UV_CACHE_DIR=.uv-cache uv run pytest apps/api/tests/test_api_local_data.py apps/api/tests/test_api_entities.py apps/api/tests/test_api_transactions.py -q
  ```

  **Commit:** `improve synthetic demo`

## Serve focused views from the API

- [ ] **Task 6: Add scoped, grouped evidence readers for people, places, and review**

  **Files:**
  - Modify: `apps/api/spend_memory/api/contracts.py`
  - Modify: `apps/api/spend_memory/enrichment/repository.py`
  - Modify: `apps/api/spend_memory/api/routes/entities.py`
  - Modify: `apps/web/src/lib/api.ts`
  - Test: `apps/api/tests/test_api_entities.py`
  - Test: `apps/web/src/lib/api.test.ts` if present

  **Interfaces:**
  - Extend existing entity endpoints with the shared transaction scope fields: `after`, `before`, `account`, `currency`, `direction`, and text query where applicable.
  - Return grouped responses rather than a raw card for every transaction. A person/place group contains display name, kind, transaction count, last activity date, received/sent/net per currency, and a short recent-activity list.
  - Keep a clearly separate review result for unresolved labels and candidates. Do not label unresolved statement text as a confirmed person or place.

  **Steps:**
  1. Add tests for filtering entity evidence to January, including a January 1 row, and excluding other months.
  2. Add a test proving multiple transactions for one merchant return one group with deterministic per-currency totals.
  3. Implement grouped SQL/repository results using decimal-safe database aggregation. Keep exact money calculation in the backend.
  4. Reuse the existing query contract types where possible. Do not create a second scope syntax.
  5. Ensure empty results return an empty collection and a plain explanation, never a fake card.
  6. Run entity and counterparty API tests.

  **Commit:** `group activity evidence`

- [ ] **Task 7: Return comparison options and a useful default comparison**

  **Files:**
  - Modify: `apps/api/spend_memory/api/routes/compare.py` or the existing comparison route
  - Modify: `apps/api/spend_memory/api/contracts.py`
  - Modify: `apps/web/src/lib/api.ts`
  - Test: `apps/api/tests/test_api_compare.py` or the existing comparison test file
  - Test: `apps/web/src/components/comparison-view.test.tsx`

  **Steps:**
  1. Write a failing API test with the demo account/currency pair and a valid April-vs-March comparison that has deterministic changes.
  2. Return valid account/currency choices with the comparison response or context response. Do not make the page infer values from a blank form.
  3. Make missing selection choose the first valid local pair when data exists. Preserve a deliberately selected pair and show native selects for changing it.
  4. Keep comparison explanation server-derived. It should name the categories or merchants that account for the exact deterministic difference.
  5. Test no-data and single-month states with useful guidance instead of an inactive-looking page.

  **Commit:** `improve comparison defaults`

## Repair the web experience

- [ ] **Task 8: Add a reusable result summary below activity results**

  **Files:**
  - Modify: `apps/web/src/components/transaction-ledger.tsx`
  - Modify: `apps/web/src/components/lens-summary.tsx`
  - Modify: `apps/web/src/app/page.tsx`
  - Modify: `apps/web/src/app/page.css` or the current global stylesheet
  - Test: `apps/web/src/components/transaction-ledger.test.tsx`
  - Test: `apps/web/src/app/page.test.tsx`

  **Rendering contract:** After the final activity row and before the result count, show a concise “Result summary” with API lens values for count, sent, received, and net. Render each currency separately. For zero results, show zero entries and no invented money figures.

  **Steps:**
  1. Write a failing ledger test with a typed lens containing AED and USD values. Assert exact formatted amounts and placement after rows.
  2. Pass the same scoped lens already loaded for the table into the ledger. If pagination exists, label clearly that the summary covers all matching entries, not only this page.
  3. Do not calculate totals from visible rows in React.
  4. Make the summary keyboard-readable and visually quiet, with a clear border separating it from results.
  5. Test a text search, direction filter, and empty result case.

  **Commit:** `show result summaries`

- [ ] **Task 9: Rebuild activity controls as responsive control groups**

  **Files:**
  - Modify: `apps/web/src/components/filter-controls.tsx`
  - Modify: `apps/web/src/app/page.css` or the current global stylesheet
  - Test: `apps/web/src/components/filter-controls.test.tsx`
  - Test: `apps/web/e2e/activity-layout.spec.ts` (new)

  **Design:** Use a dedicated search row. Put account, currency, direction, sort, and order in a wrapping field group. Keep optional controls inside a labelled disclosure. Apply button sits at the end of its group, never under one unrelated field. On narrow screens fields stack in document order with full-width controls.

  **Steps:**
  1. Add a component test asserting labels and controls remain independently accessible, including expanded optional filters.
  2. Remove fixed grid tracks that conflict with native input minimum width. Use `minmax(0, ...)`, `flex-wrap`, and intentional breakpoints.
  3. Add Playwright visual/geometry checks at 1600, 1280, 1024, 768, and 390 pixels. Assert each labelled control’s box does not overlap any other control and document body does not gain horizontal overflow.
  4. Keep the existing readable typography and colour palette. Do not introduce a dashboard component library.
  5. Run page, filter, and new layout tests locally before accepting a screenshot baseline.

  **Commit:** `fix activity controls`

- [ ] **Task 10: Make People & places a genuine discovery screen**

  **Files:**
  - Modify: `apps/web/src/components/merchant-view.tsx`
  - Modify: `apps/web/src/app/page.tsx`
  - Modify: `apps/web/src/app/page.css` or the current global stylesheet
  - Test: `apps/web/src/components/merchant-view.test.tsx`
  - Test: `apps/web/e2e/demo.spec.ts`

  **Steps:**
  1. Replace transaction-shaped merchant cards with the grouped evidence from Task 6.
  2. Give the screen three clear sections: people and transfers, places and merchants, and needs review. Only show a section when it has meaningful results.
  3. Each card shows name, evidence status, count, last activity, sent, received, and net. A single action opens filtered trusted activity for that group.
  4. Hide raw normalised descriptors and duplicated description text from ordinary cards. Keep raw evidence on the record detail/review path only.
  5. Test that one repeated merchant is one card and unresolved labels appear only in needs review.

  **Commit:** `focus people and places`

- [ ] **Task 11: Make patterns and compare explain actual data**

  **Files:**
  - Modify: `apps/web/src/components/recurring-view.tsx`
  - Modify: `apps/web/src/components/review-view.tsx`
  - Modify: `apps/web/src/components/comparison-view.tsx`
  - Modify: `apps/web/src/app/page.tsx`
  - Test: `apps/web/src/components/recurring-view.test.tsx`
  - Test: `apps/web/src/components/comparison-view.test.tsx`

  **Steps:**
  1. Render a recurring section only when the scoped API reports candidates. Replace repeating scope text with a one-sentence explanation and the candidate evidence.
  2. Render duplicate/review work only when candidates exist. Show an intentional empty state otherwise.
  3. Use Task 7 valid account/currency defaults in comparison. Explain the exact current-versus-prior change with the top contributing evidence.
  4. Make every route use the same scope heading, so a user can tell whether they are seeing April, a custom period, or all data.
  5. Test the demo produces meaningful cards for patterns and a non-empty comparison, while an empty workspace stays calm and useful.

  **Commit:** `clarify patterns and compare`

## Documentation, full verification, and handoff

- [ ] **Task 12: Make local setup and privacy promises accurate**

  **Files:**
  - Modify: `README.md`
  - Modify: `docs/` setup or architecture documentation if present
  - Test: Docker Compose commands manually

  **Steps:**
  1. Document Docker Desktop as the supported prerequisite and show `docker --version` plus `docker compose version` checks.
  2. Include one command path for the synthetic demo and one for importing a user statement. State which browser URL to open and how to reset demo safely.
  3. Explain that statements and the DuckDB file stay in the local Docker volume or configured local data directory. Do not claim uploads are disabled in the local app because import is a core local feature.
  4. Explain that hosted demos, if ever made, must use synthetic data and must disable uploads.
  5. Avoid undocumented package-manager prerequisites. If Node tooling is optional, say so. Do not make pnpm installation a required Docker user step.

  **Verification:**
  ```bash
  docker compose config
  docker compose up --build -d
  docker compose ps
  ```

  **Commit:** `improve local setup`

- [ ] **Task 13: Run the full quality gate and inspect the finished browser flows**

  **Files:**
  - Modify only test snapshots that have an intentional, reviewed visual change.
  - Do not change product code in this task. Create a follow-up task if a check exposes a defect.

  **Steps:**
  1. Run API tests, web unit tests, lint, production build, and all Playwright tests.
  2. Start the Compose stack from a fresh local data volume only if it is safe to do so. Verify synthetic demo, search, result summaries, people and places, patterns, comparison, and a synthetic statement import through the browser.
  3. Inspect the five required viewport widths. Confirm no field overlap, clipped labels, horizontal page overflow, or empty default demo page.
  4. Run `git diff --check`, a Ponytail review, and a final manual scan for raw statement descriptors escaping into high-level discovery cards.
  5. Record exact commands and outcomes in the PR body. Do not claim a check passed unless it completed successfully.

  **Commands:**
  ```bash
  UV_CACHE_DIR=.uv-cache uv run pytest apps/api/tests -q
  pnpm --dir apps/web test -- --runInBand
  pnpm --dir apps/web lint
  pnpm --dir apps/web build
  pnpm --dir apps/web exec playwright test
  git diff --check
  ```

  **Commit:** `verify product repair` only if approved snapshot or documentation evidence changed; otherwise no commit.

- [ ] **Task 14: Review, publish, and merge safely**

  **Steps:**
  1. Review every diff against this plan, including API contract compatibility and local-data privacy boundaries.
  2. Confirm all commits use the configured Hassan Git identity and no bot attribution.
  3. Push the feature branch and create or update a public GitHub pull request.
  4. Wait for GitHub Actions. Investigate any failed check from its logs before merging. Do not merge solely because local checks passed.
  5. After approval and green CI, merge the PR with a normal merge commit and confirm `main` contains the changes.

  **Commit:** No new implementation commit.

## Dependency order

```text
Task 1 test scaffolding
  -> Task 2 date correctness
  -> Task 3 workspace context
  -> Task 4 valid defaults
  -> Task 5 meaningful demo
  -> Tasks 6 and 7 API read models
  -> Tasks 8, 9, 10, and 11 web repair
  -> Task 12 documentation
  -> Task 13 full verification
  -> Task 14 PR and merge
```

Tasks 6 and 7 can be developed in separate worktrees after Task 5. Tasks 8 and 9 can proceed in parallel once the contracts they consume are stable. Merge each independently tested unit before the final browser verification.

## Plan self-review checklist

- [x] Exact money and all result totals remain server-derived and deterministic.
- [x] The date boundary is explicitly shared by search, counters, entities, and SQL readers.
- [x] Demo quality uses the ordinary local import and refresh pipeline, not fake frontend values.
- [x] Every user-facing repair has an automated test or an explicit browser verification step.
- [x] Responsive geometry is checked at each viewport where the reported defect occurs.
- [x] Docker and local-only guidance are included without adding new services.
- [x] Each independently working unit has a natural, short commit message.
