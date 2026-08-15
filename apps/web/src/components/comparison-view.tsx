import type { PeriodExplanation, WorkspaceContext } from "../lib/api";
import type { WorkspaceState } from "../lib/url-state";
import type { Dispatch } from "react";
import { formatMoney } from "../lib/format";
import { RecordChart } from "./chart";

type ComparisonViewProps = {
  accounts: WorkspaceContext["accounts"];
  account?: string;
  currency?: string;
  hasWorkspace: boolean;
  hasPreviousPeriod: boolean;
  comparison?: PeriodExplanation;
  loadError?: string;
  onScopeChange: Dispatch<Partial<WorkspaceState>>;
};

export function ComparisonView({ accounts, account, currency, hasWorkspace, hasPreviousPeriod, comparison, loadError, onScopeChange }: Readonly<ComparisonViewProps>) {
  const selectedAccount = accounts.find((option) => option.account === account);
  const activeCurrency = currency ?? "";
  const validPair = Boolean(selectedAccount?.currencies.includes(activeCurrency));
  const controls = hasWorkspace && <form className="filter-controls" onSubmit={(event) => event.preventDefault()}>
    <label>Account<select aria-label="Account" value={selectedAccount?.account ?? ""} onChange={(event) => { const next = accounts.find((option) => option.account === event.target.value); onScopeChange({ account: next?.account, currency: next?.currencies[0] }); }}><option value="">Choose an account</option>{accounts.map((option) => <option key={option.account} value={option.account}>{option.account}</option>)}</select></label>
    <label>Currency<select aria-label="Currency" value={validPair ? activeCurrency : ""} disabled={!selectedAccount} onChange={(event) => onScopeChange({ currency: event.target.value || undefined })}><option value="">Choose a currency</option>{selectedAccount?.currencies.map((option) => <option key={option} value={option}>{option}</option>)}</select></label>
  </form>;
  const heading = <><p className="eyebrow">Compare</p><h1 id="comparison-title">What changed?</h1>{controls}</>;

  if (!hasWorkspace) return <section className="record-view" aria-labelledby="comparison-title">{heading}<p className="empty-note">There is no local activity to compare yet.</p></section>;
  if (!validPair) return <section className="record-view" aria-labelledby="comparison-title">{heading}<p className="empty-note">Choose a valid account and currency from the available local activity.</p></section>;
  if (!hasPreviousPeriod) return <section className="record-view" aria-labelledby="comparison-title">{heading}<p className="empty-note">An earlier matching period is needed before this month can be compared.</p></section>;
  if (loadError) return <section className="record-view" aria-labelledby="comparison-title">{heading}<p className="empty-note" role="status">{loadError}</p></section>;
  if (!comparison) return <section className="record-view" aria-labelledby="comparison-title">{heading}<p className="empty-note" role="status">Loading the exact comparison.</p></section>;
  return <section className="record-view" aria-labelledby="comparison-title">{heading}<p className="intro">{comparison.text}</p><dl className="comparison-totals" aria-label="Exact comparison totals"><div><dt>Earlier net</dt><dd>{formatMoney(comparison.before_net_amount_minor, activeCurrency)}</dd></div><div><dt>Later net</dt><dd>{formatMoney(comparison.after_net_amount_minor, activeCurrency)}</dd></div><div><dt>Exact change</dt><dd>{formatMoney(comparison.difference_net_amount_minor, activeCurrency)}</dd></div></dl><RecordChart title="Waterfall text alternative" values={comparison.contributions.map((contribution) => ({ label: contribution.label, value: formatMoney(contribution.amount_minor, activeCurrency) }))} /><table className="contribution-table"><caption>Exact contribution evidence</caption><thead><tr><th scope="col">Contributor</th><th scope="col">Change</th><th scope="col">Evidence rows</th></tr></thead><tbody>{comparison.contributions.map((contribution) => <tr key={contribution.label}><th scope="row">{contribution.label}</th><td>{formatMoney(contribution.amount_minor, activeCurrency)}</td><td>{contribution.before_transaction_ids.length + contribution.after_transaction_ids.length}</td></tr>)}</tbody></table></section>;
}
