# Milestone 4 enrichment design

## Purpose

Milestone 4 turns trusted transaction facts into useful local signals. It adds merchant resolution, categories, recurring-payment candidates, possible duplicate and unusual-spend candidates, search, and exact period-change explanations.

This work keeps financial facts separate from interpretations. Imported documents and raw records remain immutable. Reconciled analytics marts remain the source for balances and totals. Enrichment records are local annotations with their source transaction IDs, method version, confidence, and supporting evidence.

## Scope boundary

Milestone 4 covers Tasks 10 through 15 of the implementation plan. It implements the local engines, persistence, and tests.

The original Task 15 mentions an API route. API routes belong to Milestone 5, so Milestone 4 supplies a pure period-explanation service and its tests. Milestone 5 will expose that service through FastAPI.

No UI or HTTP endpoint is added in this milestone.

## Binding decisions

- All enrichment is local. There are no online lookups, external datasets, merchant-reference packs, or hosted inference services.
- Synthetic labelled fixtures are used for automated evaluation. Real statements and user corrections stay local and are never committed, uploaded, or used to train a shared model.
- Rules are the default. A lightweight local model is only allowed when its held-out evaluation clearly beats the matching rule baseline for the same job.
- A suggestion is never treated as a confirmed fact. Only user-confirmed aliases, merchant categories, and transaction overrides affect downstream categorisation and analysis.
- Money calculations stay deterministic and use integer minor units in SQL or typed application code. ML and similarity scoring never calculate money.
- The first useful version is preferred over a speculative platform. New abstractions, integrations, and model dependencies need a measured use case.

## Local data and lineage

Milestone 4 adds small local persistence tables through the existing migration path. They store corrections and candidate annotations, not replacements for source data.

Confirmed merchant aliases map a normalized statement descriptor to a local merchant identity. Category data has user-editable categories, merchant assignments, and transaction-level overrides. Candidate records for recurring payments, duplicates, and unusual activity keep a state such as `candidate`, their evidence, confidence, and the method version that produced them.

Every enrichment output references the applicable canonical transaction or reconciled mart row. It also records enough evidence to explain why it was produced. Examples include the matched alias, text score, observed intervals, amount range, or robust historical comparison. Candidate data never changes a transaction amount, direction, date, or import result.

Suggestions do not need a durable feedback system before there is a user action that consumes them. Persist confirmed local corrections and meaningful candidate evidence only.

## Merchant resolution

Merchant resolution is a local, evidence-first pipeline:

1. Normalize descriptor text by applying documented casing, punctuation, payment-prefix, transaction-ID, and terminal-code rules.
2. Resolve exact matches against user-confirmed local aliases.
3. For unresolved descriptors, retrieve candidates from locally confirmed aliases and merchant names with character n-gram TF-IDF.
4. Rank candidates with text similarity, compatible currency, and prior local corrections.
5. Return an explicit unresolved result below the configured suggestion threshold.

Raw location is not currently available as a reliable source field, so it is not invented as a ranking signal. It can be evaluated later if a supported statement format provides it consistently.

Exact alias matches are confirmed. Retrieval results are suggestions only, even when their score is high. A human confirmation is required before a new alias becomes a future exact match.

Evaluation uses a merchant-level split so variants of the same merchant cannot leak between training and evaluation. It reports precision, recall, coverage, and confidence calibration beside a deterministic normalization and exact-alias baseline.

## Categories

Category precedence is deterministic:

1. A confirmed transaction-level override wins.
2. A confirmed category assigned to the resolved merchant applies next.
3. Otherwise the transaction is `Uncategorized`.

Categories are user-editable local labels. Merchant-resolution suggestions do not assign a category. A local classifier is optional only after enough confirmed labels exist and a held-out merchant-level evaluation shows a meaningful improvement over the rule baseline. Its version and confidence must be recorded, and low-confidence output remains uncategorized.

## Recurring payments

Recurring analysis groups debit transactions by confirmed merchant when available, otherwise by normalized descriptor, currency, and direction. It detects monthly, weekly, quarterly, and annual patterns using interval tolerance, amount tolerance, and descriptor consistency.

The first implementation is rules-based and produces candidates, not automatic subscriptions. Each candidate explains its observed dates, amount range, cadence, and expected next window. A classifier is only considered after the rule evaluation shows a real gap on labelled synthetic cases.

## Possible duplicates and unusual spending

Duplicate detection adds evidence to possible transaction pairs. It scores matching or near-matching merchant or normalized descriptor, amount, currency, direction, and time distance. It must preserve legitimate repeated purchases, refunds, and reversals as distinct outcomes when the evidence does not support a duplicate candidate.

Unusual-spend detection is a personal-history signal, not fraud detection. It uses robust per-merchant or descriptor statistics such as a median and median absolute deviation, and returns no result when history is too thin. Both duplicate and unusual outputs are review candidates only. They never hide, delete, or alter transactions.

## Search

Search starts with the parts that can be evaluated and explained locally:

- structured filters for date, amount, direction, currency, merchant, category, and candidate state;
- a small documented query grammar for combining those filters with free text;
- lexical search over raw and normalized descriptions; and
- a deterministic ranker that combines exact filter matches with lexical relevance.

An on-device semantic retrieval layer is deferred behind evidence. It must not call a hosted service or download a model during normal use. It is only added when the local lexical baseline has been compared with a 50-query synthetic evaluation set and the semantic layer gives a clear, measured improvement without harming understandable search behaviour.

## Exact period-change explanations

The period-explanation service compares two explicit date ranges and produces a fixed-language explanation from deterministic aggregates. It calculates the total change in SQL, then decomposes it into one-off, recurring, merchant, and category contributions where confirmed enrichment exists. Unresolved transactions remain visible under their raw or normalized descriptor.

The service proves that the displayed contributions sum exactly to the observed difference, including an explicit remainder when grouping cannot fully explain it. It returns the figures and evidence used by the template. It does not use an LLM for arithmetic or narrative generation.

## Testing and acceptance evidence

Tests will be written first and will cover the public behaviour of each engine and its migration-backed persistence. Fixtures are synthetic and include messy descriptors, known aliases, category precedence, recurring patterns, true duplicates, legitimate repeats, refunds, reversals, sparse histories, search queries, and reconciled period comparisons.

Required evidence includes:

- merchant-level evaluation splits and the baseline comparison;
- precision, recall, coverage, and calibration for merchant suggestions;
- deterministic category precedence and low-confidence fallback;
- recurring-candidate explanations and expected windows;
- duplicate and unusual-spend cases that avoid false claims;
- a 50-query local search evaluation before semantic retrieval is considered; and
- exact reconciliation of every period explanation to the source-period totals.

All existing import, reconciliation, analytics, API, web, and CI checks must remain green. Test data must never contain a real statement or reusable personal financial information.

## Non-goals

Milestone 4 does not add external reference data, remote ML, automatic financial decisions, fraud claims, payment or banking integrations, authentication, cloud storage, a user interface, or API routes. It also does not make speculative suggestions permanent without a local user confirmation.
