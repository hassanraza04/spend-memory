# Focused product repair design

## Purpose

Spend Memory currently has its local ingestion and analysis pieces, but its demo
and working interface do not reliably explain a person's spending. This repair
makes the existing local product coherent. It fixes exact scope calculations,
gives every filtered result a useful summary, supplies a realistic synthetic
demo, and replaces data dumps and dead ends with focused working views.

This is not a new product or a visual reskin. It preserves the local-only
architecture, deterministic monetary calculations, current routes, and the
existing import, enrichment, source evidence, grouping, export, and deletion
boundaries.

## Audit findings

The product audit on 2026-08-13 found these confirmed defects:

- The ledger filter grid gives controls less width than native inputs require.
  Account overlaps Currency and Currency overlaps Direction at 1600, 1280,
  1024, 768, and mobile widths. Tablet also creates horizontal page overflow.
- Active searches and filters show rows and a count but no sent, received, net,
  or currency-separated total.
- Date filtering uses an exclusive start and exclusive end. A displayed range
  from `2026-01-01` to `2026-02-01` excludes activity on 1 January. The same
  incorrect predicate is used by transactions, search, counterparty filtering,
  and period comparison.
- The demo has one month of activity, 18 unresolved merchants, zero categories,
  zero recurring candidates, and zero review candidates. It cannot demonstrate
  the capability described by the product or README.
- The app defaults to the calendar month even when local data exists only in a
  different period, which opens an apparently empty record.
- People & places renders a repeated unresolved-label grid with technical
  evidence fields rather than grouped people and merchants.
- Patterns has empty recurring and review sections in the default demo.
- Compare requires a hand-entered account and currency, so its primary link is
  a dead end for normal use.
- Entity routes return whole-record rows while their screens combine them with
  selected-scope summary language.

Current automated checks pass, but they do not cover these behaviors. The
repair adds direct coverage for them.

## Product direction

The product should feel like a private personal record, not an analytics
dashboard. The visual language remains warm and editorial, but the working
surface becomes compact and calm.

- Design variance: 4. The page structure should be familiar and stable.
- Motion intensity: 2. Interactions get simple focus, hover, and pressed
  feedback only.
- Visual density: 6. Financial rows and summaries are readable without large
  decorative gaps or generic cards.

The primary questions are:

1. What happened in this period?
2. Which transactions match what I remember?
3. Who or what is behind this activity?
4. Which payments repeat or deserve review?
5. What changed between two periods?

## Exact scope rules

All route and UI date scopes use a half-open interval:

```text
[after, before)
```

`after` is included and `before` is excluded. A month scope from 1 January to
1 February includes all 1-31 January activity. This convention applies to:

- transaction list and search;
- server-side lens summaries;
- counterparty scope filtering;
- recurring and review memberships when their visible transaction evidence is
  scoped; and
- both periods in period comparison.

No browser code totals money. The API returns currency-separated integer-minor
unit summaries and the UI only formats them.

## Workspace context and defaults

Add one read-only local workspace-context response. It returns:

- earliest and latest trusted activity date;
- available accounts;
- available currencies, including the accounts in which they occur; and
- the latest month containing trusted activity.

If a URL has no explicit date scope, the UI uses the latest active month. If a
URL has an explicit scope, it preserves it exactly, including an empty scope.
The overview heading reflects the selected period. For a one-month range it
uses `What happened in January?`; for other ranges it uses `What happened in
this period?` followed by the visible date range.

The context response is advisory only. Every API query still validates its own
filters and derives its own deterministic totals.

## Synthetic demo

The local demo is a deterministic multi-month AED statement. It is marked as
demo data and remains isolated from real imports under the existing safety
rules.

It contains enough history to demonstrate the product without pretending to be
real financial data:

- January through April 2026 activity for one synthetic account and currency;
- confirmed aliases for several intentionally messy statement descriptors;
- confirmed categories for everyday spending, transport, media, groceries, and
  insurance;
- a monthly Streambox payment with at least three observations;
- one clear possible duplicate pair;
- some unresolved labels that appear only in a focused review section; and
- enough monthly variation to produce a useful period comparison.

Demo setup seeds only local merchant and category annotations. It runs the
existing refresh pipeline so recurring and review candidates are generated by
the same production rules as real imports. The demo must not contain manually
inserted analytics totals or browser-only fixture behavior.

## Shared result-summary contract

The existing `WorkspaceLens` contract is the canonical summary shape. Every
transaction query that renders a ledger also fetches the lens for the exact
same filters and date scope.

The ledger renders a `Result summary` directly after its rows and before the
entry count. For each currency it shows:

- sent;
- received;
- net flow; and
- entries.

It is present for an unfiltered list, text search, any individual filter, and
every filter combination. If no rows match, it says that there is no matching
activity and does not invent a zero-value currency card.

This summary uses the same server response as overview and focused lenses. It
does not sum rows in React, and it is not affected by pagination.

## Screen behavior

### Overview

The overview contains a compact period control, an exact currency summary,
one short interpretation based only on the returned data, category totals when
confirmed categories exist, and a clear route to Compare. The compare route
carries the selected account and currency when there is only one valid choice.

If the scope has multiple accounts or currencies, the overview presents a
small chooser before opening the explanation. It never links to a blank
comparison screen.

### Activity

Activity is the main working surface.

- Search occupies its own full row.
- Account, currency, direction, sort, and order use a second responsive row.
- Advanced filters live in an expandable section below those controls.
- At wide widths the controls use CSS grid columns with `minmax(0, 1fr)` and
  all inputs and selects use `width: 100%; min-width: 0`.
- At tablet and mobile widths the grid intentionally becomes one or two
  columns. It never relies on native control overflow.
- Apply remains an explicit action. Enter in Search submits the same form.
- The result summary follows the ledger table on every response.

Rows use a resolved merchant or original description once, not twice. The raw
statement descriptor, method, confidence, source text, and internal evidence
remain in the selected transaction's detail panel.

### People & places

This screen has two meaningful sections.

1. `People`: saved counterparties, each with sent, received, net, entries, and
   a link that opens their exact transaction scope.
2. `Places`: resolved merchants, grouped by merchant rather than one card per
   transaction. Each row shows the merchant, category where confirmed, total
   outgoing flow, entry count, and a link to matching activity.

Unresolved statement labels do not dominate the screen. A small `Needs review`
section shows unique labels, occurrence counts, and a path to correct an alias.
Technical key names are never visible in the normal screen.

Each section uses the active scope. Whole-record history can be stated only
when explicitly selected by a separate control.

### Patterns

Patterns contains recurring payments and review items in distinct sections.
Recurring rows show merchant or descriptor, typical amount range, cadence,
observations, and the next expected window. Review rows identify possible
duplicates or unusual activity and provide their evidence in normal language.

When there is insufficient history, the screen explains that no recurring
patterns are available yet and names the minimum requirement. It does not show
an empty chart or a duplicated workspace total.

### Compare

Compare gets valid account, currency, and date defaults from workspace context.
For a single account and currency it loads immediately. For multiple choices,
it renders a small labeled form with available options and a Compare action.
It shows exact earlier total, later total, difference, and contribution rows.
It never asks a person to infer the exact identifier to type.

### Data

The existing export and exact-deletion confirmation behavior stays unchanged.
Export continues to use the current exact scope.

## API boundaries

The repair keeps existing local routes stable where possible.

- Fix all shared date predicates at the search and period-row boundaries.
- Ensure list, search, and lens use the same filter model and half-open scope.
- Add a workspace-context route rather than adding client-side inference.
- Extend focused entity queries only when needed to honor active scope.
- Add a grouped merchant/counterparty view from repository data rather than
  grouping transactions in the browser.
- Continue to use database writes only for annotations, never for calculated
  money.

No authentication, cloud storage, external enrichment, banking integration,
hosted data, payment system, or new paid dependency is part of this work.

## Error, empty, and safety states

- Loading states reserve the shape of their final content.
- A scoped empty ledger states the active scope and offers a clear way to
  change it.
- A failed local request identifies the affected section and keeps unrelated
  working data visible.
- All destructive actions retain their existing exact confirmation.
- Demo and real imports remain mutually exclusive.
- Existing source evidence and correction paths remain available.

## Verification requirements

### Unit and API tests

- A transaction on the start date appears in list, search, lens, counterparty,
  and comparison calculations.
- A transaction on the end date does not appear.
- The same filtered scope returns matching list totals and lens totals.
- Filter summaries cover text, account, currency, direction, amount, merchant,
  category, counterparty, and review state.
- Workspace context reports valid activity ranges, accounts, currencies, and
  latest active month.
- The demo produces confirmed merchant/category data, at least one recurring
  candidate, at least one review candidate, and a comparison with exact
  contribution evidence.

### Component tests

- Activity renders a result summary after filters and shows no fabricated zero
  cards for no-result scopes.
- People groups merchants and counterparties and does not expose technical
  evidence key names.
- Patterns gives useful empty states and renders demo candidates when present.
- Compare chooses a valid default or presents labeled selections.
- Overview names its actual period and links to a valid comparison.

### Browser and visual tests

- Exercise the synthetic demo from a fresh local record.
- Search and filter activity, then assert the summary has exact totals.
- Open merchant, counterparty, recurring, review, and compare journeys.
- At 1600, 1280, 1024, 768, and 390 pixels, assert no filter-control bounding
  rectangles overlap and page width does not exceed viewport width.
- Verify keyboard navigation, visible focus, form labels, and selected-row
  interaction.
- Capture updated synthetic-only visual snapshots for desktop, tablet, and
  mobile.

## Scope boundaries

This repair deliberately does not add budgets, forecasting, bank connections,
automatic real-person matching, online merchant lookup, receipts, mobile apps,
or cloud synchronization. It improves the existing questions with data the
local record can support.
