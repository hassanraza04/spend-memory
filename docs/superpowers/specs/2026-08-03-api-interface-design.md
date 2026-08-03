# Milestone 5 API and interface design

## Purpose

Milestone 5 turns Spend Memory's local ingestion, analytics, and enrichment work into a usable local product. It provides a versioned FastAPI boundary, a desktop-first Next.js interface, and end-to-end synthetic workflows.

The product begins with a choice to import a statement or explore a synthetic demo. Once data exists, the default view answers one question first: "What happened this month?" The user can then inspect the rows and source evidence that support the answer.

## Scope

This design covers Tasks 16, 17, 18, and 18A of the implementation plan.

It adds:

- a local REST API at `/api/v1`;
- import, transaction, merchant, category, recurring, review, search, comparison, export, demo, and deletion workflows;
- a Personal Record visual theme with an optional Night Desk theme;
- an exploratory lens pattern for a search term, account, merchant, category, recurring group, review state, or saved counterparty;
- local counterparties that users can create, group transactions under, and match through confirmed aliases;
- browser tests and Playwright workflows using only synthetic data; and
- an adapter conformance boundary and parser-debug UI for future input types.

Milestone 5 does not add authentication, cloud storage, banking connections, payments, shared accounts, remote analytics, hosted inference, mobile apps, or a production hosting path for uploads. The API remains local and financial data never leaves the device.

## Existing boundaries that remain binding

- `IngestionService.import_document` remains the sole production entry point for untrusted document bytes.
- Source documents, raw transactions, canonical amounts, directions, and import results remain immutable.
- The API and UI read trusted financial data from `analytics.mart_transactions`. They do not include unreconciled imports in totals, lenses, charts, or comparisons.
- Canonical money is a non-negative integer `amount_minor` plus `direction`. All arithmetic stays in deterministic Python or SQL. The browser formats amounts but does not calculate them.
- Merchant suggestions, recurring candidates, duplicate candidates, unusual-spend candidates, and text matches remain suggestions or review signals. They do not change financial facts.
- Every amount shown in an interface summary must be traceable to its included transaction IDs and source-document location.
- Cross-currency arithmetic is forbidden. Summaries are grouped by currency unless a future explicit exchange-rate policy is designed and approved.

## Product structure

### First run

An empty local database opens on a working start screen, not a marketing page. It shows two actions:

1. **Import a statement** is the primary action. It accepts a supported CSV or PDF, explains that the data stays local, and begins the existing safe-ingress workflow.
2. **Explore the synthetic demo** is a visible secondary action. It creates only synthetic local records and labels the workspace as demo data. Before a user can import personal data, the UI requires them to clear the demo records. The user can also delete local data from settings.

The UI does not claim an exact import percentage. It shows truthful stages such as "Checking file", "Reading statement", "Reconciling import", and "Preparing your record". Unsupported, partial, failed, and duplicate imports explain what happened and what the user can do next.

### Main navigation

Desktop navigation uses these stable labels:

- **This month**: default overview for the active range.
- **All activity**: searchable transaction ledger and source inspection.
- **People & places**: counterparties and merchants.
- **Patterns**: recurring payments, categories, and review candidates.
- **Compare**: exact period-to-period explanations.
- **Data**: imports, exports, local preferences, and deletion.

On narrow screens, navigation becomes a horizontally accessible section strip. Each main view has a single-column layout. The selected date range, currency, account, filter set, query, and selected transaction persist while the user moves between views.

### Monthly overview

The overview asks "What happened this month?" It contains:

- an active date range and account or currency scope;
- spending and received totals by currency;
- a concise deterministic explanation of the largest period changes;
- one monthly or weekly trend chart only when it answers the selected range question;
- a link to the exact comparison detail; and
- the most relevant transaction rows directly below the answer.

The overview does not repeat category composition and merchant composition charts. Those appear only in their focused lens where they answer a different question.

### Transaction ledger and source inspection

The ledger is the core working surface. It supports text search, date, account, currency, direction, amount, merchant, category, counterparty, and review-state filters. Users can sort by date, amount, merchant, or confidence and choose from a small set of saved local column presets.

Each row includes the raw statement description, normalized or resolved name when available, amount, direction, currency, source page or row, and clear status for confirmed versus suggested enrichment. Selecting a row opens a source-aware side panel. The panel shows the raw description, source file and location, extraction confidence where available, merchant and category corrections, counterparty assignment, recurring and review evidence, and a link to related transactions.

### Flexible lenses

A lens is the shared way Spend Memory answers a scoped question without creating a separate dashboard for every entity type.

An ad hoc lens is created from a search or filter. For example, searching a person's name or choosing an account opens all matching trusted transactions and shows, for each currency:

- money sent, from debit transactions;
- money received, from credit transactions;
- net flow, calculated as received minus sent;
- transaction count and date coverage;
- an appropriate time trend; and
- the included rows and their source evidence.

A saved lens is available for merchants, categories, recurring groups, review states, and counterparties. It preserves the same summary pattern while adding focused detail. A merchant lens shows aliases and recurring candidates. A category lens shows contributors. A recurring lens shows observed payments, cadence, and expected window. A review lens shows evidence and a safe resolution action.

### Counterparties

Counterparties are private local labels for a person or account. They are not bank contacts and are never sent outside the device.

Users can create a counterparty, select one or more trusted transactions, and assign them to that counterparty. An assigned transaction has at most one confirmed primary counterparty. Reassigning it changes only the local annotation and leaves the original statement untouched.

Users can also confirm a normalized descriptor as a counterparty alias. Future trusted transactions with that exact alias resolve to the same counterparty during local refresh. Fuzzy text results remain search results and are not automatically saved as an alias.

The counterparty detail lens shows sent, received, net flow, count, trend, source evidence, aliases, and the complete transaction list. Its totals are separated by currency.

The local persistence model adds only the records needed for this behavior:

- `counterparties` stores a UUID and user label;
- `counterparty_aliases` maps a normalized descriptor to one confirmed counterparty; and
- `transaction_counterparty_assignments` maps a trusted raw transaction ID to one counterparty.

The repository enforces that a transaction can be assigned only when it is present in the trusted transaction mart. These annotations do not modify raw or canonical transaction fields.

## Visual language

### Personal Record and Night Desk

Personal Record is the default theme. It uses a soft off-white surface, deep navy navigation, blue-grey working text, and a restrained warm amber action color. Night Desk is a persistent user preference that uses charcoal surfaces, teal evidence accents, and the same amber action color. Theme switching changes no content, filters, selection, or route.

The design is a calm editorial workspace, not a generic analytics template or a marketing landing page. It uses compact tables, clear grouping, one focused chart per question, and source evidence close to each result. Major grouped panels use a subtle nested surface treatment. Ordinary data remains in open rows with spacing and minimal separators rather than repeated cards.

The web app uses an open-source self-hosted serif for overview questions and explanations, plus Geist Sans for controls and tables. It does not load fonts at runtime from a CDN. Icons come from a maintained open-source icon package with light line weight.

The interface defines semantic tokens for surface, elevated surface, navigation, primary text, muted text, evidence, action, destructive action, and focus state. Both themes meet WCAG AA contrast. The radius rule is simple: inputs and small controls use 8px corners, grouped panels use 14px corners, and primary actions use pills.

### Motion and accessibility

Motion is limited to feedback and state changes: a short theme transition, a filter drawer, a source panel, selection, and save confirmation. It uses transform and opacity only, supports `prefers-reduced-motion`, and never blocks a financial action. Keyboard users can reach every control, close every panel with Escape, inspect rows, and see an obvious focus outline. Tables retain useful labels and actions on mobile instead of hiding essential information.

### States and writing

Empty states explain the next useful action. Loading states preserve the shape of the pending table or summary. Errors use plain language, name the affected action, and do not expose parser internals or financial descriptions in logs. Copy is direct: "Import a statement", "Review this match", "Show source", and "Delete local data".

## API design

### Transport rules

The API is local REST JSON at `/api/v1` with FastAPI-generated OpenAPI documentation. It binds to `127.0.0.1` by default. There is no authentication, public deployment configuration, or permissive CORS policy.

Every collection accepts bounded `limit` and `offset`, explicit allowed sort keys and order, and typed filters. Defaults are safe and small. Invalid filters return a stable error envelope:

```json
{
  "error": {
    "code": "invalid_filter",
    "message": "The date range is not valid.",
    "details": [{"field": "after", "code": "after_must_precede_before"}]
  }
}
```

Pydantic request and response models define all public fields. UUIDs and dates use their standard JSON representation. Money travels as `amount_minor`, `currency`, and `direction`, not as floating-point values or formatted strings.

### Routes

| Route | Purpose |
| --- | --- |
| `POST /api/v1/imports` | Safely import a supported local file and return its import result. |
| `GET /api/v1/imports/{id}` | Inspect import status, reconciliation, and safe metadata. |
| `POST /api/v1/imports/{id}/reprocess` | Retry a known stored import through the safe ingress boundary. |
| `GET /api/v1/transactions` | List trusted transactions with filters, sort, paging, annotations, and source references. |
| `PATCH /api/v1/transactions/{id}` | Confirm a transaction-level category or counterparty assignment. |
| `GET /api/v1/merchants` | List and filter confirmed merchants and suggestions. |
| `PATCH /api/v1/merchants/{id}` | Update a local merchant correction or category assignment. |
| `GET /api/v1/categories` | List confirmed local categories and their currency-separated scoped summaries. |
| `GET /api/v1/counterparties` | List local counterparties and their scoped summaries. |
| `POST /api/v1/counterparties` | Create a local counterparty label. |
| `PATCH /api/v1/counterparties/{id}` | Rename a counterparty or confirm an exact descriptor alias. |
| `POST /api/v1/counterparties/{id}/transactions` | Assign selected trusted transaction IDs to one counterparty. |
| `GET /api/v1/counterparties/{id}/lens` | Return currency-separated sent, received, net, trend, rows, and evidence. |
| `GET /api/v1/recurring` | List active recurring candidates with membership and expected-window evidence. |
| `GET /api/v1/review` | List duplicate and unusual-spend candidates without changing transactions. |
| `GET /api/v1/search` | Return lexical results, structured-filter results, and an ad hoc currency-separated lens summary. |
| `GET /api/v1/comparisons` | Return exact period explanations and contribution lineage. |
| `POST /api/v1/demo/reset` | Reset synthetic local demo data only. It rejects a workspace containing a non-demo import and never accepts uploaded data. |
| `GET /api/v1/exports/transactions.csv` | Download the active trusted transaction scope as a safe CSV. |
| `DELETE /api/v1/local-data` | Delete local application data after an exact confirmation string. |

The search and transaction list add `account` and `counterparty` filters to the existing enrichment filter set. An ad hoc search lens covers the selected result scope, so a text search can immediately show all matching transactions and deterministic totals without creating a saved group.

Import responses trigger the existing local analytics and enrichment refresh only after the import is reconciled. Duplicate documents retain existing idempotent import behavior. Import errors expose a safe code and user action, not worker details.

`DELETE /api/v1/local-data` requires `{ "confirmation": "DELETE LOCAL DATA" }`. CSV export protects spreadsheet users by prefixing cells that begin with formula characters. The API does not log raw descriptions, full filenames, document bytes, or request bodies at normal log levels.

## Application boundaries

The API layer has small route modules, Pydantic contracts, dependency providers, and error translation. It delegates to the existing `ImportRepository`, `IngestionService`, `EnrichmentRepository`, `EnrichmentService`, lexical search, and period-explanation service. It must not issue ad hoc DuckDB queries in route handlers.

The counterparty repository is a focused extension of the enrichment persistence boundary. A pure counterparty lens service receives trusted rows and confirmed assignments, performs integer-minor-unit aggregation by currency, and returns immutable result records. The API serializes those records. The UI does not duplicate the aggregation logic.

The web app keeps a single URL-backed view state for date range, account, currency, query, filters, selected transaction, and theme. Local storage holds only harmless preferences such as theme and table column preset. It does not store imported statement bytes or a second copy of financial data.

## Testing and acceptance evidence

Tests are written before implementation changes.

### API tests

- FastAPI `TestClient` tests cover every route, request contract, response contract, validation failure, not-found result, paging, sorting, and error envelope.
- Import tests prove the API uses `IngestionService.import_document`, observes request-size boundaries, keeps retries idempotent, and returns safe failure messages.
- Search tests cover text, date, account, currency, direction, amount, merchant, category, counterparty, and review filters.
- Comparison tests prove contribution values reconcile exactly to the reported period difference.
- Counterparty tests cover manual grouping, exact alias reuse, reassignment, trusted-row-only enforcement, received and sent totals, net flow, and separate currency outputs.
- Export tests prove formula injection is neutralized. Local deletion tests require the exact confirmation body.

### Interface tests

- Component tests cover the first-run choice, table filtering, source inspection, counterparty grouping, theme persistence, search lens totals, empty and error states, and accessible keyboard behavior.
- The UI must preserve active scope when switching views. It must label synthetic data and suggestions clearly.
- Focused chart tests verify the monthly trend, comparison waterfall, and recurring timeline render only with suitable data and have accessible text alternatives.

### End-to-end tests

Playwright uses synthetic fixtures only. It covers: start demo and search a known purchase; import a CSV and verify reconciliation; import a scanned PDF through OCR; correct a merchant and observe exact alias reuse; group a person or account and verify sent, received, and net values; inspect a recurring payment; compare two months and verify exact contributions; re-import without duplication; export transactions; and delete all local data.

Tests run at common laptop, wide desktop, tablet, and narrow mobile viewports. Screenshot review checks overlap, truncation, keyboard-visible focus, unusable controls, and chart failures.

### Input expansion

Task 18A adds adapter conformance tests, capability metadata, parser-debug rows before import, and experimental disabled-by-default receipt-image and transaction-screenshot adapters using synthetic fixtures. New parser adapters must not change canonical storage, analytics, enrichment, or UI contracts. Documentation explains how to add a bank-specific CSV or PDF parser.

## Verification and handoff

Each independently complete unit follows TDD, receives focused tests, and is committed and pushed with a short natural message. Before an M5 review, the branch runs API tests, web tests, lint, analytics build, and the relevant Playwright suite successfully. No completion claim is made before those checks pass.

This design introduces no remote service, paid dependency, external merchant reference source, or model download. It keeps flexibility where it helps a person answer a real question and avoids general-purpose dashboard configuration.
