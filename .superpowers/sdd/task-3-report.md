# Task 3 report: imports, transactions, search, and lenses

## Delivered

- Added versioned import, transaction, search, and counterparty-assignment routes.
- Kept uploads on `IngestionService.import_document`; the route forwards only document bytes, filename, and declared MIME type.
- Added explicit Pydantic request and response contracts for paging, typed filters, source evidence, currency flows, imports, and counterparty assignment.
- Added injected ingestion and enrichment dependencies, with no route-level DuckDB queries.
- Added a trusted-mart repository projection that joins only local confirmed annotations and source evidence.
- Extended lexical search with exact account and counterparty filters without changing its deterministic ranker.
- Calculated transaction and counterparty lenses server-side, from trusted rows, using integer minor units separated by currency.
- Added `python-multipart`, the FastAPI-required multipart parser, with no unrelated dependencies.

## TDD evidence

The requested API test files did not exist at the start, so the initial focused pytest command failed with missing test paths. New behavior tests were then added before the route implementation. The initial implementation run exposed an empty transaction scope, which was corrected by allowing the existing ranker to include an untextual filtered scope for the ledger route.

## Verification

```text
uv run pytest apps/api/tests/test_api_imports.py apps/api/tests/test_api_transactions.py apps/api/tests/test_api_search.py apps/api/tests/test_api_counterparties.py apps/api/tests/test_transaction_search.py apps/api/tests/test_counterparties.py apps/api/tests/test_counterparty_lenses.py -v
18 passed

uv run ruff check apps/api
All checks passed!
```

The API tests include a real synthetic CSV import and idempotent retry through the configured ingress, a trusted-mart transaction integration check, request validation, safe import errors, source evidence, structured account search, debit and credit AED lens flow, counterparty grouping, missing counterparties, duplicate IDs, and untrusted assignments.

## Concerns and follow-up

- Importing a document still does not initiate an analytics or enrichment refresh. That lifecycle behavior belongs to a later orchestration task.
- The existing repository and API error envelope use generic `invalid_request` for Pydantic validation details. No validation error exposes exception text.
