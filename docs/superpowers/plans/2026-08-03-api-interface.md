# Milestone 5 API and Interface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Spend Memory's local API, flexible transaction lenses, polished desktop-first interface, and synthetic end-to-end workflows.

**Architecture:** Keep route handlers thin. Typed FastAPI contracts call focused local services and repositories, while a single URL-backed React workspace consumes those contracts. Add counterparties as confirmed local annotations, and calculate every lens summary from trusted canonical transactions grouped by currency.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, DuckDB, pytest, Next.js 16, React 19, TypeScript, Vitest, Testing Library, Playwright, CSS variables, and only free open-source packages.

## Global Constraints

- Use Ponytail full. Reuse existing services, DuckDB migrations, CSS, and browser APIs before adding abstractions or dependencies.
- Follow TDD: every production behavior begins with a focused test that fails for the intended missing behavior.
- Do not modify source documents, raw transactions, canonical amounts, direction, or reconciliation outcomes.
- Read financial rows only from `analytics.mart_transactions`. Calculations use integer minor units and keep currencies separate.
- `IngestionService.import_document` is the only production route for uploaded document bytes.
- Bind the API to localhost by default. No authentication, public CORS, cloud storage, remote calls, or hosted models.
- Pydantic validates every public request. Parameterize every DuckDB query. Return safe error envelopes and never log descriptions, filenames, bytes, SQL, or worker details at normal log level.
- Use synthetic data only in tests, demo reset, screenshots, and committed fixtures.
- Use Personal Record by default and persist the optional Night Desk preference locally. Keep filters, range, and selection in URL state.
- Meet keyboard navigation, visible focus, WCAG AA contrast, mobile single-column behavior, and reduced-motion support.
- Run focused tests after each task. Before review run `make test`, `make lint`, the configured analytics build, and Playwright.
- Commit and push each independent task with a short natural message. Work on `feature/api-interface` in a fresh worktree.

---

## File structure

- `apps/api/spend_memory/storage/migrations/0006_counterparties.sql`: additive local counterparty tables. The repository performs trusted-row enforcement in its shared write transaction.
- `apps/api/spend_memory/enrichment/models.py`: immutable counterparty and currency-flow records.
- `apps/api/spend_memory/enrichment/counterparties.py`: pure integer-based counterparty and ad hoc lens aggregation.
- `apps/api/spend_memory/enrichment/repository.py`: counterparty persistence, trusted transaction projections, and source-aware list queries.
- `apps/api/spend_memory/api/contracts.py`: Pydantic input and output contracts.
- `apps/api/spend_memory/api/dependencies.py`: configured local repository and service dependencies.
- `apps/api/spend_memory/api/errors.py`: one exception mapping and error envelope.
- `apps/api/spend_memory/api/routes/*.py`: small import, transaction, entity, search, comparison, export, demo, and data route modules.
- `apps/api/app/main.py`: `create_app` composition and only route registration.
- `apps/api/tests/test_api_*.py`: TestClient behavior-first API coverage.
- `apps/web/src/app/*`: workspace routes and layout.
- `apps/web/src/components/*`: focused shell, ledger, source panel, lens, import, chart, and settings components.
- `apps/web/src/lib/api.ts`, `apps/web/src/lib/format.ts`, and `apps/web/src/lib/url-state.ts`: one typed API client, deterministic display formatting, and URL state parsing.
- `apps/web/tests/e2e/*` and `apps/web/playwright.config.ts`: local synthetic Playwright workflows and screenshot settings.
- `docs/adding-a-parser.md`: adapter contract and parser-debug instructions.

## Task 1: Create the local API foundation

**Files:**
- Create: `apps/api/spend_memory/api/__init__.py`, `contracts.py`, `dependencies.py`, `errors.py`
- Create: `apps/api/tests/test_api_errors.py`, `test_api_health.py`
- Modify: `apps/api/app/main.py`

**Interfaces:**
- Produces `create_app(database_path: Path, data_directory: Path) -> FastAPI` and `ApiError(code, message, status_code, details=())`.
- Produces `ErrorResponse(error: ErrorBody)` and `Page[T](items: list[T], limit: int, offset: int, total: int)`.

- [ ] Write a failing TestClient test that `GET /api/v1/health` returns `{"status": "ok"}` and an unknown route returns the error envelope without debug detail.
- [ ] Run `uv run pytest apps/api/tests/test_api_health.py apps/api/tests/test_api_errors.py -v` and confirm failure because the versioned app and exception handler do not exist.
- [ ] Add only app composition, local settings dependencies, the `/api/v1/health` route, request validation translation, `ApiError`, and a safe unexpected-error response. Leave storage queries out of handlers.
- [ ] Re-run the focused tests and confirm they pass.
- [ ] Add failing tests for `limit` values below 1 or above 100, invalid `offset`, invalid UUID path values, and unsupported sort keys. Add shared Pydantic bounds and explicit enums until they pass.
- [ ] Commit `add api foundation` and push the feature branch.

## Task 2: Add counterparty annotations and deterministic lenses

**Files:**
- Create: `apps/api/spend_memory/storage/migrations/0006_counterparties.sql`
- Create: `apps/api/spend_memory/enrichment/counterparties.py`
- Modify: `apps/api/spend_memory/enrichment/models.py`, `repository.py`
- Create: `apps/api/tests/test_counterparties.py`, `test_counterparty_lenses.py`

**Interfaces:**
- Produces `Counterparty(counterparty_id: UUID, label: str)`.
- Produces `CurrencyFlow(currency: str, sent_minor: int, received_minor: int, net_minor: int, transaction_count: int)`.
- Produces `summarize_lens(transactions: Iterable[TrustedTransaction]) -> tuple[CurrencyFlow, ...]` where debit contributes to sent, credit contributes to received, and `net_minor == received_minor - sent_minor`.
- Produces repository methods `create_counterparty`, `confirm_counterparty_alias`, `assign_counterparty_transactions`, `find_counterparty`, and `list_counterparty_transactions`.

- [ ] Write failing migration tests asserting that counterparties, aliases, and assignments are additive, each normalized alias maps to one counterparty, and a raw transaction can have one assignment.
- [ ] Write failing lens tests using AED and PKR rows. Assert AED and PKR have separate totals, debit and credit are never summed together as spend, and assignment of an ID absent from `analytics.mart_transactions` raises `trusted_transaction_required`.
- [ ] Run `uv run pytest apps/api/tests/test_counterparties.py apps/api/tests/test_counterparty_lenses.py -v` and confirm failure before the migration and service exist.
- [ ] Add the three tables with UUID primary keys, foreign keys, timestamps, unique normalized alias, and unique raw-transaction assignment. Do not backfill or alter financial rows. Use the existing migration runner.
- [ ] Add repository methods with parameterized SQL and a trusted-mart membership check in the shared write transaction. Add the smallest pure aggregation function grouped by currency.
- [ ] Re-run focused tests, then `uv run pytest apps/api/tests/test_enrichment_repository.py apps/api/tests/test_counterparties.py apps/api/tests/test_counterparty_lenses.py -v`.
- [ ] Commit `add counterparties` and push.

## Task 3: Expose imports, transactions, search, and lenses

**Files:**
- Create: `apps/api/spend_memory/api/routes/imports.py`, `transactions.py`, `search.py`, `counterparties.py`
- Modify: `apps/api/spend_memory/api/contracts.py`, `dependencies.py`, `apps/api/app/main.py`
- Create: `apps/api/tests/test_api_imports.py`, `test_api_transactions.py`, `test_api_search.py`, `test_api_counterparties.py`

**Interfaces:**
- `POST /api/v1/imports` receives one multipart file and passes bytes, filename, and MIME type only to `IngestionService.import_document`.
- `GET /api/v1/transactions` accepts typed `after`, `before`, `account`, `currency`, `direction`, `amount_min_minor`, `amount_max_minor`, `merchant`, `category`, `counterparty`, `state`, `sort`, `order`, `limit`, and `offset`.
- `GET /api/v1/search` returns `{query, items, lens}` where `lens` is a tuple of `CurrencyFlow` for exactly the returned filtered scope before pagination.
- `POST /api/v1/counterparties/{id}/transactions` receives `{"transaction_ids": [UUID, ...]}` and returns the updated counterparty lens.

- [ ] Write failing API tests for a safe CSV import, duplicate retry, oversized upload rejection, valid transaction paging, source evidence presence, structured search, account filtering, ad hoc AED flow, and counterparty grouping.
- [ ] Run `uv run pytest apps/api/tests/test_api_imports.py apps/api/tests/test_api_transactions.py apps/api/tests/test_api_search.py apps/api/tests/test_api_counterparties.py -v` and confirm the routes are absent.
- [ ] Implement narrow route modules that depend on injected services and serialize explicit response models. Map known `ImportRepositoryError` and domain errors to safe `ApiError` codes. Never return exception text.
- [ ] Extend the existing lexical search filter model for `account` and `counterparty`, keeping its deterministic text ranker and using the same trusted rows for list and lens results.
- [ ] Re-run focused tests. Add negative tests for missing multipart file, invalid enum, no matching counterparty, duplicate IDs, untrusted assignment, and a lens containing both debit and credit.
- [ ] Commit `add transaction api` and push.

## Task 4: Expose enrichment, comparison, export, demo, and deletion routes

**Files:**
- Create: `apps/api/spend_memory/api/routes/entities.py`, `comparison.py`, `exports.py`, `local_data.py`
- Modify: `contracts.py`, `dependencies.py`, `app/main.py`, `pyproject.toml` only if a required free package is missing
- Create: `apps/api/tests/test_api_entities.py`, `test_api_comparisons.py`, `test_api_exports.py`, `test_api_local_data.py`

**Interfaces:**
- `GET /api/v1/merchants`, `/categories`, `/recurring`, and `/review` return candidate evidence and status without mutating transactions.
- `GET /api/v1/comparisons` takes two explicit non-overlapping date ranges and returns the existing `PeriodExplanation` with contribution transaction IDs.
- `GET /api/v1/exports/transactions.csv` returns the active trusted scope and neutralizes cells beginning `=`, `+`, `-`, or `@`.
- `POST /api/v1/demo/reset` rejects non-demo imports. `DELETE /api/v1/local-data` accepts only `{"confirmation":"DELETE LOCAL DATA"}`.

- [ ] Write failing TestClient tests for each list response, merchant correction, category override, recurring memberships, duplicate evidence, exact comparison reconciliation, CSV formula escaping, demo reset rejection with a real import, and deletion confirmation rejection.
- [ ] Run the four focused API test files and confirm the routes fail before implementation.
- [ ] Add route modules and repository or service queries needed by the contracts. Reuse active recurring generation readers. Keep destructive operations in explicit service methods with a single confirmation check.
- [ ] Re-run focused tests and `make analytics-test` to prove confirmed annotations remain factual and candidates remain non-factual.
- [ ] Perform the API review checklist: Pydantic input bounds, parameterized SQL, explicit DTOs, safe errors, upload limits, localhost binding, restricted CORS, and redacted normal logs.
- [ ] Commit `finish local api` and push.

## Task 5: Build the app shell, tokens, and first-run workflow

**Files:**
- Modify: `apps/web/src/app/layout.tsx`, `page.tsx`
- Create: `apps/web/src/app/globals.css`, `src/components/app-shell.tsx`, `first-run.tsx`, `theme-toggle.tsx`, `src/lib/api.ts`, `url-state.ts`, `format.ts`
- Modify: `apps/web/src/app/page.test.tsx`; create `apps/web/src/components/first-run.test.tsx`

**Interfaces:**
- Produces `ApiClient` methods matching the versioned contracts, with no duplicate arithmetic in the browser.
- Produces `WorkspaceState` parsed from `URLSearchParams` and preserves date range, account, currency, query, filters, and selected transaction across links.
- Produces `ThemeToggle` using local storage key `spend-memory-theme`, defaulting to `personal-record`.

- [ ] Write failing component tests for the import and demo choices, local-only copy, Personal Record default, Night Desk persistence, and a keyboard-reachable navigation strip.
- [ ] Run `pnpm --dir apps/web test -- first-run app-shell` and confirm failure because components and tokens are absent.
- [ ] Add CSS semantic tokens for both themes, a consistent radius scale, visible focus styles, and `prefers-reduced-motion` behavior. Use CSS and native controls before new UI dependencies.
- [ ] Add a compact responsive shell. It must use the approved navigation labels, keep the first screen functional, and render loading, empty, unsupported-file, partial-import, and failed-import states.
- [ ] Re-run focused tests and `pnpm --dir apps/web lint`.
- [ ] Commit `build app shell` and push.

## Task 6: Build the overview, ledger, source inspection, and flexible lenses

**Files:**
- Create: `apps/web/src/components/month-overview.tsx`, `transaction-ledger.tsx`, `filter-controls.tsx`, `source-panel.tsx`, `lens-summary.tsx`, `counterparty-editor.tsx`
- Create: component tests beside each component
- Modify: `apps/web/src/app/page.tsx`, `src/lib/api.ts`, `src/lib/url-state.ts`

**Interfaces:**
- `LensSummary` receives currency-separated API flows and formats display values only.
- `TransactionLedger` receives paged API data and emits URL-state updates for filter, sort, and selected row.
- `CounterpartyEditor` creates a label, assigns selected rows, and confirms an exact alias only after an explicit user action.

- [ ] Write failing tests for the monthly question, currency-separated sent/received/net display, text search, account filter, retained URL scope, source panel evidence, row keyboard selection, and manual counterparty grouping.
- [ ] Run the focused Vitest files and confirm each fails before its component exists.
- [ ] Implement the overview with one appropriate trend chart, a link to comparison, and relevant transaction rows. Build the ledger with native table semantics, small saved column presets, filters, and source panel.
- [ ] Implement ad hoc and saved lenses from API results. Do not add a client-side query evaluator or currency conversion. Add local column-preset persistence only after the table works.
- [ ] Re-run focused tests at desktop and narrow jsdom viewport assumptions. Run `pnpm --dir apps/web lint`.
- [ ] Commit `build flexible lenses` and push.

## Task 7: Build focused entity, pattern, comparison, and data views

**Files:**
- Create: `apps/web/src/components/merchant-view.tsx`, `recurring-view.tsx`, `review-view.tsx`, `comparison-view.tsx`, `data-view.tsx`, `chart.tsx`
- Create: matching Vitest files
- Modify: `apps/web/src/app/page.tsx`, `src/lib/api.ts`

**Interfaces:**
- Merchant, category, counterparty, recurring, and review views consume the same `LensSummary` contract.
- `ComparisonView` displays server-provided integer contribution values and checks nothing beyond rendering the provided exact result.
- `DataView` requires a typed destructive confirmation before calling local-data deletion.

- [ ] Write failing tests for confirmed versus suggested labels, recurring expected dates, review evidence, comparison contribution table and waterfall text alternative, export link, and deletion confirmation.
- [ ] Run focused web tests and confirm failure before view components exist.
- [ ] Implement one chart per view question. Use accessible SVG or HTML with a text equivalent, never a charting library unless the existing browser APIs cannot meet the tested requirement.
- [ ] Add correction controls with inline validation and explicit saving states. Ensure active URL scope survives view changes and all dialogs close with Escape.
- [ ] Re-run focused tests, `pnpm --dir apps/web test`, and `pnpm --dir apps/web lint`.
- [ ] Commit `build record views` and push.

## Task 8: Add Playwright workflows and visual review

**Files:**
- Modify: `apps/web/package.json`, `pnpm-lock.yaml`, `Makefile`, CI workflow if one exists
- Create: `apps/web/playwright.config.ts`, `apps/web/tests/e2e/fixtures.ts`, `demo.spec.ts`, `import.spec.ts`, `review.spec.ts`, `comparison.spec.ts`, `data.spec.ts`

**Interfaces:**
- Playwright starts the local API and web app against an isolated synthetic data directory per test worker.
- Tests use role, label, and test-id locators. They use web-first assertions, not arbitrary waits.

- [ ] Add the free `@playwright/test` development dependency and test scripts only after a failing `pnpm --dir apps/web exec playwright test` proves the runner is absent.
- [ ] Write a failing demo journey: start synthetic demo, search a known purchase, open source evidence, group a counterparty, and assert currency-separated sent, received, and net values.
- [ ] Write failing import and review journeys: CSV reconciliation, scanned PDF OCR, merchant correction and alias reuse, recurring inspection, exact month comparison, duplicate re-import, CSV export, and exact local-data deletion confirmation.
- [ ] Implement isolated fixtures and deterministic synthetic setup. Do not mock the local API for these end-to-end flows.
- [ ] Add screenshot assertions at laptop, wide desktop, tablet, and narrow mobile widths. Inspect failures for overlap, clipping, hidden controls, and chart unreadability.
- [ ] Run `pnpm --dir apps/web exec playwright test --reporter=list`, then repeat the critical flows five times before accepting them as stable.
- [ ] Commit `test local workflows` and push.

## Task 9: Add parser conformance and complete verification

**Files:**
- Create: `apps/api/tests/test_parser_conformance.py`, `apps/api/spend_memory/ingestion/conformance.py`, `docs/adding-a-parser.md`
- Modify: parser registry contracts, import response contract, and import UI parser-debug component
- Create: synthetic receipt-image and screenshot fixture adapters, disabled by default

**Interfaces:**
- Every parser exposes capability metadata for text extraction, OCR need, balance support, currency discovery, confidence, and experimental status.
- `assert_parser_conforms(parser, fixture)` checks typed rows, source locations, canonical conversion boundary, and safe error behavior.

- [ ] Write failing conformance tests for current parsers and disabled experimental adapters. Include a test proving an adapter cannot bypass safe ingress or change canonical storage contracts.
- [ ] Run `uv run pytest apps/api/tests/test_parser_conformance.py -v` and confirm failure before the conformance utility exists.
- [ ] Add the minimal metadata and shared conformance helper. Keep experimental receipt and screenshot adapters out of automatic parser selection.
- [ ] Add a parser-debug view that displays detected synthetic rows before the user commits an import. It must show source locations and warnings without exposing a hidden automatic correction.
- [ ] Re-run focused parser and UI tests. Then run `make test`, `make lint`, `make analytics-test`, the configured `make analytics` command with an explicit temporary DuckDB path, and the full Playwright suite.
- [ ] Run Ponytail review. Remove unneeded abstractions and dependencies, while retaining validation, local safety, accessibility, and deterministic money behavior.
- [ ] Commit `extend local inputs` and push.

## Final review checklist

- [ ] Every new test was observed failing before its production code was added.
- [ ] All API responses use explicit Pydantic models and all errors share the stable envelope.
- [ ] All lens values reconcile to trusted transaction rows and are separated by currency.
- [ ] Counterparty assignment and alias reuse only create local annotations.
- [ ] No route exposes raw files, worker detail, SQL, stack traces, or sensitive normal logs.
- [ ] The interface works with keyboard navigation, reduced motion, both themes, and narrow mobile widths.
- [ ] Every Playwright fixture, screenshot, and demo record is synthetic.
- [ ] No hosted upload, cloud dependency, auth system, reference dataset, model download, or monetary ML calculation was introduced.
