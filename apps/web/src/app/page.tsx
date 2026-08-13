"use client";

import { useEffect, useRef, useState } from "react";

import { AppShell } from "../components/app-shell";
import { CounterpartyEditor } from "../components/counterparty-editor";
import { FirstRun } from "../components/first-run";
import { MerchantView } from "../components/merchant-view";
import { MonthOverview } from "../components/month-overview";
import { RecurringView } from "../components/recurring-view";
import { ReviewView } from "../components/review-view";
import { ComparisonView } from "../components/comparison-view";
import { DataView } from "../components/data-view";
import { SourcePanel } from "../components/source-panel";
import { TransactionLedger } from "../components/transaction-ledger";
import { ApiClient, localErrorMessage, type Category, type MerchantEvidence, type Page as ApiPage, type PeriodExplanation, type RecurringCandidate, type ReviewCandidate, type Transaction, type WorkspaceLens } from "../lib/api";
import { mergeWorkspaceState, toWorkspaceHref, workspaceStateFrom, workspaceViewFrom, type WorkspaceState } from "../lib/url-state";

const api = new ApiClient();
const demoWorkspaceKey = "spend-memory-demo-workspace";

function apiScope(state: WorkspaceState): Record<string, string | undefined> {
  return { after: state.after, before: state.before, account: state.account, currency: state.currency, direction: state.direction, amount_min_minor: state.amountMinMinor, amount_max_minor: state.amountMaxMinor, merchant: state.merchant, category: state.category, counterparty: state.counterparty, state: state.state, sort: state.sort, order: state.order, limit: state.limit, offset: state.offset };
}

function comparisonScope(state: WorkspaceState): Record<string, string | undefined> {
  if (!state.after || !state.before || !state.account || !state.currency) return {};
  const start = Date.parse(`${state.after}T00:00:00Z`);
  const end = Date.parse(`${state.before}T00:00:00Z`);
  if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) return {};
  return { before_start: new Date(start - (end - start)).toISOString().slice(0, 10), before_end: state.after, after_start: state.after, after_end: state.before, account: state.account, currency: state.currency };
}

export default function Page() {
  const [state, setState] = useState<WorkspaceState>(() => typeof window === "undefined" ? {} : workspaceStateFrom(new URLSearchParams(window.location.search)));
  const stateRef = useRef(state);
  const shouldDefaultScope = useRef(!state.after && !state.before);
  const activityLoad = useRef(0);
  const [contextReady, setContextReady] = useState(() => Boolean(state.after || state.before));
  const [transactions, setTransactions] = useState<ApiPage<Transaction> | null>(null);
  const [lens, setLens] = useState<WorkspaceLens | null>(null);
  const [hasWorkspace, setHasWorkspace] = useState<boolean | null>(null);
  const [selected, setSelected] = useState<Transaction | null>(null);
  const [groupIds, setGroupIds] = useState<string[]>([]);
  const [merchants, setMerchants] = useState<MerchantEvidence[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [recurring, setRecurring] = useState<RecurringCandidate[]>([]);
  const [review, setReview] = useState<ReviewCandidate[]>([]);
  const [merchantError, setMerchantError] = useState<string>();
  const [recurringError, setRecurringError] = useState<string>();
  const [reviewError, setReviewError] = useState<string>();
  const [comparisonError, setComparisonError] = useState<{ key: string; message: string }>();
  const [comparison, setComparison] = useState<{ key: string; value: PeriodExplanation }>();
  const [activityRevision, setActivityRevision] = useState(0);
  const [contextRevision, setContextRevision] = useState(0);
  const view = typeof window === "undefined" ? "this-month" : workspaceViewFrom(new URLSearchParams(window.location.search));

  useEffect(() => { stateRef.current = state; }, [state]);

  useEffect(() => {
    if (!shouldDefaultScope.current) { setContextReady(true); return; }
    let current = true;
    void api.getWorkspaceContext().then((context) => {
      if (!current) return;
      const currentState = stateRef.current;
      if (shouldDefaultScope.current && !currentState.after && !currentState.before && context.latestMonthStart && context.latestMonthEnd) {
        const next = { ...currentState, after: context.latestMonthStart, before: context.latestMonthEnd };
        shouldDefaultScope.current = false;
        window.history.replaceState({}, "", toWorkspaceHref(next, view));
        setState(next);
      }
      setContextReady(true);
    }).catch(() => { if (current) setContextReady(true); });
    return () => { current = false; };
  }, [contextRevision, view]);

  useEffect(() => {
    if (!contextReady) return;
    const loadId = ++activityLoad.current;
    let current = true;
    const scope = apiScope(state);
    const workspace = api.listTransactions({ limit: "1" });
    const load = state.query
      ? Promise.all([api.searchTransactions({ ...scope, query: state.query }), workspace]).then(([result, all]) => ({ page: { items: result.items, total: result.items.length, limit: result.items.length || 1, offset: 0 }, lens: { lens: result.lens, trend: [] }, hasWorkspace: all.total > 0 }))
      : Promise.all([api.listTransactions(scope), api.getLens(scope), workspace]).then(([page, nextLens, all]) => ({ page, lens: nextLens, hasWorkspace: all.total > 0 }));
    void load.then((result) => { if (current && loadId === activityLoad.current) { setTransactions(result.page); setLens(result.lens); setHasWorkspace(result.hasWorkspace); } }).catch(() => { if (current && loadId === activityLoad.current) { setTransactions(null); setLens(null); setHasWorkspace(false); } });
    return () => { current = false; };
  }, [activityRevision, contextReady, state]);

  useEffect(() => {
    if (!hasWorkspace) return;
    let current = true;
    if (view === "people-places") void Promise.all([api.listMerchants(), api.listCategories()]).then(([nextMerchants, nextCategories]) => { if (current) { setMerchants(nextMerchants.items); setCategories(nextCategories.items); setMerchantError(undefined); } }).catch((error) => { if (current) setMerchantError(localErrorMessage(error, "Merchant and category data could not be loaded.")); });
    if (view === "patterns") {
      void api.listRecurring().then((nextRecurring) => { if (current) { setRecurring(nextRecurring.items); setRecurringError(undefined); } }).catch((error) => { if (current) setRecurringError(localErrorMessage(error, "Recurring data could not be loaded.")); });
      void api.listReview().then((nextReview) => { if (current) { setReview(nextReview.items); setReviewError(undefined); } }).catch((error) => { if (current) setReviewError(localErrorMessage(error, "Review data could not be loaded.")); });
    }
    const periodScope = comparisonScope(state);
    const periodKey = JSON.stringify(periodScope);
    if (view === "compare") {
      if (Object.keys(periodScope).length) void api.getComparison(periodScope).then((nextComparison) => { if (current) { setComparison({ key: periodKey, value: nextComparison }); setComparisonError(undefined); } }).catch((error) => { if (current) setComparisonError({ key: periodKey, message: localErrorMessage(error, "Comparison could not be loaded.") }); });
    }
    return () => { current = false; };
  }, [activityRevision, hasWorkspace, state, view]);

  function changeScope(patch: Partial<WorkspaceState>) {
    const next = mergeWorkspaceState(state, patch);
    if ((state.after || state.before) && !next.after && !next.before) shouldDefaultScope.current = false;
    window.history.pushState({}, "", toWorkspaceHref(next, view));
    setSelected(null);
    setState(next);
  }

  function select(transaction: Transaction) {
    changeScope({ selected: transaction.transaction_id });
    setSelected(transaction);
  }

  function toggleGrouping(transactionId: string) {
    setGroupIds((ids) => ids.includes(transactionId) ? ids.filter((id) => id !== transactionId) : [...ids, transactionId]);
  }

  function refreshWorkspaceContext() {
    setContextReady(false);
    setContextRevision((value) => value + 1);
  }

  function leaveDemoWorkspace() {
    try {
      window.localStorage.removeItem(demoWorkspaceKey);
    } catch {
      // Local storage can be unavailable in private browsing.
    }
    activityLoad.current += 1;
    setContextReady(false);
    setHasWorkspace(false);
  }

  const hasRecord = hasWorkspace === true && transactions !== null && lens !== null;
  const activeSelected = selected ?? (state.selected ? transactions?.items.find((transaction) => transaction.transaction_id === state.selected) ?? null : null);
  return (
    <AppShell>
      {view === "data" && hasWorkspace !== false ? <DataView scope={apiScope(state)} onDeleted={leaveDemoWorkspace} /> : !hasRecord ? <FirstRun ready={hasWorkspace !== null} onReady={refreshWorkspaceContext} /> : <>
        {view === "this-month" && <MonthOverview lens={lens} state={state} />}
        {view === "all-activity" && <section className="view-intro"><p className="eyebrow">Your private record</p><h1>All activity</h1><p className="intro">Search a person, account, place, or anything else you remember.</p></section>}
        {view === "people-places" && <MerchantView flows={lens.lens} merchants={merchants} categories={categories} counterpartyLabel={state.counterparty} loadError={merchantError} />}
        {view === "patterns" && <><RecurringView flows={lens.lens} recurring={recurring} loadError={recurringError} /><ReviewView flows={lens.lens} review={review} loadError={reviewError} /></>}
        {view === "compare" && <ComparisonView account={state.account} currency={state.currency} comparison={comparison?.key === JSON.stringify(comparisonScope(state)) ? comparison.value : undefined} loadError={comparisonError?.key === JSON.stringify(comparisonScope(state)) ? comparisonError.message : undefined} />}
        {(view === "this-month" || view === "all-activity") && <TransactionLedger page={transactions} state={state} onScopeChange={changeScope} onSelect={select} selectedForGrouping={groupIds} onToggleGrouping={toggleGrouping} />}
        {activeSelected && <SourcePanel transaction={activeSelected} onClose={() => { setSelected(null); changeScope({ selected: undefined }); }} />}
        {groupIds.length > 0 && <CounterpartyEditor transactionIds={groupIds} descriptor={groupIds.length === 1 ? activeSelected?.description ?? "" : ""} onSaved={() => setActivityRevision((value) => value + 1)} />}
      </>}
    </AppShell>
  );
}
