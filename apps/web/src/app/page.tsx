"use client";

import { useEffect, useState } from "react";

import { AppShell } from "../components/app-shell";
import { CounterpartyEditor } from "../components/counterparty-editor";
import { FirstRun } from "../components/first-run";
import { MonthOverview } from "../components/month-overview";
import { SourcePanel } from "../components/source-panel";
import { TransactionLedger } from "../components/transaction-ledger";
import { ApiClient, type Page as ApiPage, type Transaction, type WorkspaceLens } from "../lib/api";
import { mergeWorkspaceState, toWorkspaceHref, workspaceStateFrom, workspaceViewFrom, type WorkspaceState } from "../lib/url-state";

const api = new ApiClient();

function apiScope(state: WorkspaceState): Record<string, string | undefined> {
  return { after: state.after, before: state.before, account: state.account, currency: state.currency, direction: state.direction, amount_min_minor: state.amountMinMinor, amount_max_minor: state.amountMaxMinor, merchant: state.merchant, category: state.category, counterparty: state.counterparty, state: state.state, sort: state.sort, order: state.order, limit: state.limit, offset: state.offset };
}

export default function Page() {
  const [state, setState] = useState<WorkspaceState>(() => typeof window === "undefined" ? {} : workspaceStateFrom(new URLSearchParams(window.location.search)));
  const [transactions, setTransactions] = useState<ApiPage<Transaction> | null>(null);
  const [lens, setLens] = useState<WorkspaceLens | null>(null);
  const [selected, setSelected] = useState<Transaction | null>(null);
  const [groupIds, setGroupIds] = useState<string[]>([]);
  const [revision, setRevision] = useState(0);
  const view = typeof window === "undefined" ? "this-month" : workspaceViewFrom(new URLSearchParams(window.location.search));

  useEffect(() => {
    let current = true;
    const scope = apiScope(state);
    const load = state.query
      ? api.searchTransactions({ ...scope, query: state.query }).then((result) => ({ page: { items: result.items, total: result.items.length, limit: result.items.length || 1, offset: 0 }, lens: { lens: result.lens, trend: [] } }))
      : Promise.all([api.listTransactions(scope), api.getLens(scope)]).then(([page, nextLens]) => ({ page, lens: nextLens }));
    void load.then((result) => { if (current) { setTransactions(result.page); setLens(result.lens); } }).catch(() => { if (current) { setTransactions(null); setLens(null); } });
    return () => { current = false; };
  }, [state, revision]);

  function changeScope(patch: Partial<WorkspaceState>) {
    const next = mergeWorkspaceState(state, patch);
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

  const hasRecord = transactions !== null && lens !== null && transactions.total > 0;
  return (
    <AppShell>
      {!hasRecord ? <FirstRun onReady={() => setRevision((value) => value + 1)} /> : <>
        {view === "this-month" && <MonthOverview lens={lens} state={state} />}
        {view === "all-activity" && <section className="view-intro"><p className="eyebrow">Your private record</p><h1>All activity</h1><p className="intro">Search a person, account, place, or anything else you remember.</p></section>}
        {(view === "this-month" || view === "all-activity") && <TransactionLedger page={transactions} state={state} onScopeChange={changeScope} onSelect={select} selectedForGrouping={groupIds} onToggleGrouping={toggleGrouping} />}
        {selected && <SourcePanel transaction={selected} onClose={() => { setSelected(null); changeScope({ selected: undefined }); }} />}
        {groupIds.length > 0 && <CounterpartyEditor transactionIds={groupIds} descriptor={groupIds.length === 1 ? selected?.description ?? "" : ""} onSaved={() => { setGroupIds([]); setRevision((value) => value + 1); }} />}
        {!["this-month", "all-activity"].includes(view) && <section className="coming-soon"><p className="eyebrow">Your private record</p><h1>This part of your record is next.</h1><p className="intro">Your selected scope is still held while you move through the record.</p></section>}
      </>}
    </AppShell>
  );
}
