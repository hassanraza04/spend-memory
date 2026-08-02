# Task 6 report: review candidates

## Outcome

Implemented local, deterministic review candidates only. The rules do not modify transaction, source-document, or canonical-money values. No external data, services, models, or dependencies were added.

## Scope completed

- Added `find_duplicate_candidates` in `apps/api/spend_memory/enrichment/review.py`.
  - Requires equal account, currency, direction, absolute integer amount, merchant/descriptor identity, and a maximum one-day date distance.
  - Uses a confirmed merchant ID only when present and confirmed for both matching rows. Otherwise it uses the normalized descriptor.
  - Sorts raw ID pairs and emits fixed `1.0` confidence only for complete evidence.
- Added `find_unusual_spend_candidates` in the same module.
  - Considers debit rows only and groups by account, currency, and confirmed merchant ID or normalized descriptor.
  - Uses only values from strictly earlier transaction dates, requires five observations, and applies median plus median absolute deviation with integer money inputs.
  - Emits no candidate for thin history or zero MAD, and records group key, median, MAD, observed amount, and sample size.
- Added writer-locked replacement methods for the two generated candidate tables in `apps/api/spend_memory/enrichment/repository.py`. They delete and insert only generated candidate rows within one transaction. Foreign keys preserve raw transaction lineage.
- Added local synthetic behavior and persistence tests in `apps/api/tests/test_review_candidates.py`.

## TDD record

### Red

`uv run pytest apps/api/tests/test_review_candidates.py -v` initially failed at collection with `ModuleNotFoundError: No module named 'spend_memory.enrichment.review'`.

The first implementation run then exposed the intended foreign-key boundary in persistence: a candidate cannot reference a raw transaction that was not stored. The test was updated to create synthetic source, import-run, and raw-transaction lineage before asserting persistence.

### Green

`uv run pytest apps/api/tests/test_review_candidates.py -v`

Result: `6 passed`.

Covered behavior:

- same-day equal debit candidate and stable sorted raw IDs;
- confirmed merchant identity across different normalized descriptors;
- refunds, reversals, and later legitimate repeats excluded;
- five earlier values with non-zero MAD detect the later large spend;
- thin history and zero MAD produce no candidate;
- persistence replaces only generated review rows and preserves foreign-key lineage.

## Verification

- Focused review tests: `6 passed`.
- Task-file Ruff check: passed.
- Full project tests: `173 passed`; web test: `1 passed`.
- Analytics verification: `make analytics-test`, `11 passed`.
- `git diff --check`: passed.

`make lint` did not pass because of three pre-existing findings outside Task 6:

- `apps/api/spend_memory/enrichment/recurring.py`: import formatting and `zip` versus `itertools.pairwise`.
- `apps/api/tests/test_recurring_candidates.py`: import formatting.

The Task 6 files are Ruff-clean. Those unrelated files were left untouched.

## Files changed

- `apps/api/spend_memory/enrichment/review.py` (new)
- `apps/api/spend_memory/enrichment/repository.py`
- `apps/api/tests/test_review_candidates.py` (new)
- `.superpowers/sdd/task-6-report.md` (new)

## Self-review

- Source values remain immutable. The implementation only reads typed trusted rows and writes separate candidate records.
- All monetary comparisons use integer minor units. `statistics.median` can return a float for an even-count history, but no monetary value is rounded or persisted as a computed total. The emitted median and MAD are integer for the applicable odd five-item minimum history.
- Outputs and documentation use `candidate`; they make no allegation and never alter totals or visibility.
- Matching is intentionally conservative. Equal amount alone is insufficient.
- The implementation is standard-library only and creates no refresh orchestration, API/UI, search, or future work.

## Concerns

- Candidate replacement assumes the calling refresh path supplies trusted transaction IDs that already exist in storage. The schema enforces this by design.
- A one-day duplicate window can still surface legitimate repeated purchases as candidates when every rule matches. They are review signals only and are never applied automatically.
