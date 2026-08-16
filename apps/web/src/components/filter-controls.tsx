"use client";
/* eslint-disable no-unused-vars -- the base ESLint preset does not understand TypeScript callback parameter names. */

import { useState } from "react";

import type { WorkspaceState } from "../lib/url-state";

export function FilterControls({ state, onApply }: Readonly<{ state: WorkspaceState; onApply: (patch: Partial<WorkspaceState>) => void }>) {
  const [values, setValues] = useState(state);
  const update = (key: keyof WorkspaceState, value: string) => setValues((current) => ({ ...current, [key]: value || undefined }));

  return (
    <form className="filter-controls activity-filters" onSubmit={(event) => { event.preventDefault(); onApply({ ...values, offset: undefined, selected: undefined }); }}>
      <div className="filter-search"><label>Search activity<input aria-label="Search activity" defaultValue={state.query} onChange={(event) => update("query", event.target.value)} /></label></div>
      <div className="filter-fields" role="group" aria-label="Activity filter fields">
        <label>Account<input aria-label="Account" defaultValue={state.account} onChange={(event) => update("account", event.target.value)} /></label>
        <label>Currency<input aria-label="Currency" defaultValue={state.currency} onChange={(event) => update("currency", event.target.value.toUpperCase())} /></label>
        <label>Direction
          <select aria-label="Direction" defaultValue={state.direction ?? ""} onChange={(event) => update("direction", event.target.value)}>
            <option value="">Both ways</option><option value="debit">Sent</option><option value="credit">Received</option>
          </select>
        </label>
        <label>Sort
          <select aria-label="Sort" defaultValue={state.sort ?? "date"} onChange={(event) => update("sort", event.target.value)}>
            <option value="date">Date</option><option value="amount">Amount</option><option value="merchant">Merchant</option><option value="confidence">Confidence</option>
          </select>
        </label>
        <label>Order
          <select aria-label="Order" defaultValue={state.order ?? "desc"} onChange={(event) => update("order", event.target.value)}>
            <option value="desc">Newest first</option><option value="asc">Oldest first</option>
          </select>
        </label>
      </div>
      <div className="filter-actions">
        <details className="more-filters"><summary>More filters</summary><div>
          <label>From date<input aria-label="From date" type="date" defaultValue={state.after} onChange={(event) => update("after", event.target.value)} /></label>
          <label>To date<input aria-label="To date" type="date" defaultValue={state.before} onChange={(event) => update("before", event.target.value)} /></label>
          <label>Minimum amount<input aria-label="Minimum amount" type="number" min="0" defaultValue={state.amountMinMinor} onChange={(event) => update("amountMinMinor", event.target.value)} /></label>
          <label>Maximum amount<input aria-label="Maximum amount" type="number" min="0" defaultValue={state.amountMaxMinor} onChange={(event) => update("amountMaxMinor", event.target.value)} /></label>
          <label>Merchant<input aria-label="Merchant" defaultValue={state.merchant} onChange={(event) => update("merchant", event.target.value)} /></label>
          <label>Category<input aria-label="Category" defaultValue={state.category} onChange={(event) => update("category", event.target.value)} /></label>
          <label>Counterparty<input aria-label="Counterparty" defaultValue={state.counterparty} onChange={(event) => update("counterparty", event.target.value)} /></label>
          <label>Review state<input aria-label="Review state" defaultValue={state.state} onChange={(event) => update("state", event.target.value)} /></label>
        </div></details>
        <button className="button secondary" type="submit">Apply filters</button>
      </div>
    </form>
  );
}
