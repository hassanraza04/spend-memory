import type { CurrencyFlow } from "../lib/api";
import { formatMoney } from "../lib/format";

export function LensSummary({ flows }: Readonly<{ flows: readonly CurrencyFlow[] }>) {
  if (!flows.length) return <p className="empty-note">No trusted activity matches this scope yet.</p>;

  return (
    <div className="lens-summary" aria-label="Currency-separated activity summary">
      {flows.map((flow) => (
        <dl key={flow.currency} className="currency-flow">
          <dt>{flow.currency}</dt>
          <dd><span>Sent</span>{formatMoney(flow.sent_minor, flow.currency)}</dd>
          <dd><span>Received</span>{formatMoney(flow.received_minor, flow.currency)}</dd>
          <dd><span>Net flow</span>{formatMoney(flow.net_minor, flow.currency)}</dd>
          <dd><span>Entries</span>{flow.transaction_count}</dd>
        </dl>
      ))}
    </div>
  );
}
