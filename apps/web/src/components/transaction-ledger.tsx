"use client";
/* eslint-disable no-unused-vars -- the base ESLint preset does not understand TypeScript callback parameter names. */

import { useState } from "react";

import type { Page, Transaction, WorkspaceLens } from "../lib/api";
import { formatMoney } from "../lib/format";
import type { WorkspaceState } from "../lib/url-state";
import { FilterControls } from "./filter-controls";
import { LensSummary } from "./lens-summary";

type Preset = "standard" | "compact" | "source";
const presetKey = "spend-memory-column-preset";

function initialPreset(): Preset {
  try {
    const stored = window.localStorage?.getItem(presetKey);
    return stored === "compact" || stored === "source" ? stored : "standard";
  } catch {
    return "standard";
  }
}

function savePreset(preset: Preset) {
  try { window.localStorage?.setItem(presetKey, preset); } catch { /* ponytail: a session preset is enough when storage is unavailable. */ }
}

export function TransactionLedger({ page, lens, state, onScopeChange, onSelect, selectedForGrouping = [], onToggleGrouping }: Readonly<{
  page: Page<Transaction>;
  lens: WorkspaceLens;
  state: WorkspaceState;
  onScopeChange: (patch: Partial<WorkspaceState>) => void;
  onSelect: (transaction: Transaction) => void;
  selectedForGrouping?: readonly string[];
  onToggleGrouping?: (transactionId: string) => void;
}>) {
  const [preset, setPreset] = useState<Preset>(initialPreset);
  const setColumnPreset = (value: Preset) => { setPreset(value); savePreset(value); };
  const showCategory = preset !== "compact";
  const showSource = preset === "source";
  const grouped = new Set(selectedForGrouping);

  return (
    <section className="transaction-ledger" aria-labelledby="ledger-title">
      <div className="ledger-heading"><div><p className="eyebrow">Trusted activity</p><h2 id="ledger-title">Every entry, with its evidence</h2></div><label className="preset-control">Columns<select aria-label="Column preset" value={preset} onChange={(event) => setColumnPreset(event.target.value as Preset)}><option value="standard">Standard</option><option value="compact">Compact</option><option value="source">Source</option></select></label></div>
      <FilterControls state={state} onApply={onScopeChange} />
      {page.total === 0 ? <p className="empty-note">No trusted activity matches this scope.</p> : (
        <div className="ledger-scroll"><table><caption className="visually-hidden">Trusted transaction activity</caption><thead><tr>{onToggleGrouping && <th scope="col">Group</th>}<th scope="col">Date</th><th scope="col">Activity</th>{showCategory && <th scope="col">Category</th>}<th scope="col">Direction</th><th scope="col">Amount</th>{showSource && <th scope="col">Source</th>}</tr></thead><tbody>
          {page.items.map((transaction) => <tr key={transaction.transaction_id} tabIndex={0} aria-selected={state.selected === transaction.transaction_id} onClick={() => onSelect(transaction)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onSelect(transaction); } }}>
            {onToggleGrouping && <td><input type="checkbox" aria-label={`Group ${transaction.description}`} checked={grouped.has(transaction.transaction_id)} onClick={(event) => event.stopPropagation()} onKeyDown={(event) => { if (event.key === " ") event.stopPropagation(); }} onChange={() => onToggleGrouping(transaction.transaction_id)} /></td>}<td><time dateTime={transaction.transaction_date}>{transaction.transaction_date}</time></td><td><strong>{transaction.merchant ?? transaction.description}</strong><span>{transaction.description}</span></td>{showCategory && <td>{transaction.category}</td>}<td>{transaction.direction === "debit" ? "Sent" : "Received"}</td><td>{formatMoney(transaction.amount_minor, transaction.currency)}</td>{showSource && <td>{transaction.source.document}</td>}
          </tr>)}
        </tbody></table></div>
      )}
      <section className="result-summary" role="region" aria-label="Result summary">
        <p>All matching entries are summarized below.</p>
        {lens.lens.length ? <LensSummary flows={lens.lens} /> : <p>0 matching entries.</p>}
      </section>
      <p className="ledger-count">{page.total} trusted {page.total === 1 ? "entry" : "entries"}</p>
    </section>
  );
}
