# Milestone 4 final fix report

## Scope

This pass fixed every finding from the whole-branch review. It stayed inside the local enrichment milestone. It added no dependency, route, UI, network access, or hosted inference.

## Fixes

1. Money calculations and evidence
   - Recurring amount tolerance now compares an exact integer ratio with `difference * 10 <= maximum` and records `1000` basis points.
   - Unusual-spend median and MAD calculations now stay in integer arithmetic.
   - Half-minor-unit values are preserved as `median_amount_minor_twice` and `mad_minor_twice` integers.

2. Recurring source lineage
   - `RecurringCandidate` now retains every contributing raw transaction ID.
   - Migration `0004_recurring_candidate_members.sql` adds one membership row per candidate and source transaction.
   - Refresh replacement clears member rows and candidate rows together, then writes both in one transaction.
   - Tests prove distinct source IDs remain traceable even when the stored source rows share a date.

3. Merchant evaluation
   - Evaluation metrics are calculated only from examples whose merchant ID is held out.
   - The retrieval corpus still excludes every held-out merchant variant.
   - Results now report a separate normalization and exact-alias baseline beside retrieval precision, recall, coverage, and calibration.

4. Period explanation evidence
   - `PeriodExplanation` now returns signed `PeriodContribution` records.
   - Each contributor retains its before and after raw transaction IDs.
   - The explanation also retains the complete before and after source-row ID sets used for the period totals.
   - Integer reconciliation and fixed template text remain unchanged.

5. Recorded test gaps
   - Category tests now cover a confirmed merchant with no category assignment and require `Uncategorized`.
   - The analytics test now proves the suggested merchant row contributes exactly one row and its signed amount to the uncategorized summary.
   - The migration ledger contract now includes migration `0004`.

## TDD evidence

The regression run failed in 10 expected places before implementation. The failures covered recurring source IDs, exact amount tolerance, recurring membership storage, doubled median and MAD evidence, held-out merchant evaluation, explicit baseline metrics, signed period contributors, period source IDs, and the new migration table.

After the focused implementation slices:

- `uv run pytest apps/api/tests/test_recurring_candidates.py apps/api/tests/test_enrichment_repository.py -q`: 12 passed.
- `uv run pytest apps/api/tests/test_review_candidates.py -q`: 10 passed.
- `uv run pytest apps/api/tests/test_merchant_resolution.py -q`: 14 passed.
- `uv run pytest apps/api/tests/test_period_explanations.py -q`: 6 passed.
- Combined focused regression suite: 46 passed.
- Tightened analytics category-summary test: 1 passed with dbt integration.

## Final verification

- `make test`: 190 API tests passed and 1 web test passed.
- `make lint`: Ruff and ESLint passed.
- `uv run pytest apps/api/tests/test_analytics_models.py apps/api/tests/test_enrichment_service.py -v`: 13 passed.
- `git diff --check`: passed.

The remaining output contains existing dependency deprecation warnings and an informational stale browser-mapping notice. No verification failure remains.

## Ponytail audit

The fix reuses existing domain records, refresh orchestration, repository locking, and DuckDB migrations. It adds one small membership table because evidence JSON cannot unambiguously represent candidate membership. No speculative service, classifier, dependency, route, or UI was added.
