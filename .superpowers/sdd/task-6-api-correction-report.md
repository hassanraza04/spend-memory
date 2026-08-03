# Task 6 API contract correction

## Endpoints

- `GET /api/v1/lens` accepts the existing typed transaction filters without a required text query. It returns `lens`, currency-separated sent, received, net, and count values for the complete trusted scope, plus a deterministic monthly `trend` with `period_start` and the same currency-separated fields.
- `POST /api/v1/counterparties` accepts `{ "label": string }` and creates one local counterparty label.
- `PATCH /api/v1/counterparties/{counterparty_id}` accepts `{ "descriptor": string }` and confirms that exact normalized descriptor as an alias for the existing counterparty.

## Guarantees

- Lens and trend calculations run on trusted transaction rows in the API process. They use integer minor units and never combine currencies.
- The browser receives totals and buckets only. It performs no financial calculation.
- Counterparty creation and alias confirmation are explicit local mutations. The alias endpoint has no fuzzy matching or automatic assignment path.
- New mutation DTOs reject undeclared fields and reject blank or oversized labels and descriptors.
- Route handlers use the existing injected enrichment repository and pure lens helpers. No handler issues DuckDB queries.

## TDD and verification

The new `GET /api/v1/lens`, `POST /api/v1/counterparties`, and `PATCH /api/v1/counterparties/{id}` tests first failed with 404 responses. After the minimal route, contract, and pure date-bucket changes:

```text
uv run pytest apps/api/tests/test_api_imports.py apps/api/tests/test_api_transactions.py apps/api/tests/test_api_search.py apps/api/tests/test_api_counterparties.py apps/api/tests/test_api_lenses.py apps/api/tests/test_api_entities.py apps/api/tests/test_api_comparisons.py apps/api/tests/test_api_exports.py apps/api/tests/test_api_local_data.py apps/api/tests/test_counterparty_lenses.py -v
28 passed

uv run ruff check apps/api
All checks passed!
```

The workspace-lens test proves AED and PKR flows remain separate and its monthly buckets are server-provided. The counterparty test proves both mutations require explicit requests and records only the supplied exact alias descriptor.
