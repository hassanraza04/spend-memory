import type { WorkspaceLens } from "../lib/api";
import { formatMoney } from "../lib/format";
import { toWorkspaceHref, type WorkspaceState } from "../lib/url-state";
import { LensSummary } from "./lens-summary";

export function MonthOverview({ lens, state, scope }: Readonly<{ lens: WorkspaceLens; state: WorkspaceState; scope: string }>) {
  return (
    <section className="month-overview" aria-labelledby="monthly-question">
      <p className="eyebrow">Your private record</p>
      <div className="overview-heading"><div><h1 id="monthly-question">What happened this month?</h1><p className="intro">Here is the exact trusted activity in your current scope.</p><p className="scope-note">Scope: {scope}</p></div><a className="quiet-link" href={toWorkspaceHref(state, "compare")}>Compare these periods</a></div>
      <LensSummary flows={lens.lens} />
      {lens.trend.length > 0 && <ActivityTrend trend={lens.trend} />}
    </section>
  );
}

function ActivityTrend({ trend }: Readonly<{ trend: WorkspaceLens["trend"] }>) {
  const byCurrency = new Map<string, WorkspaceLens["trend"]>();
  for (const bucket of trend) byCurrency.set(bucket.currency, [...(byCurrency.get(bucket.currency) ?? []), bucket]);
  return (
    <section className="activity-trend" aria-labelledby="activity-trend-title">
      <div><p className="eyebrow">Through time</p><h2 id="activity-trend-title">Monthly activity</h2></div>
      {Array.from(byCurrency, ([currency, buckets]) => <CurrencyTrend key={currency} currency={currency} buckets={buckets} />)}
    </section>
  );
}

function CurrencyTrend({ currency, buckets }: Readonly<{ currency: string; buckets: WorkspaceLens["trend"] }>) {
  const highest = Math.max(0, ...buckets.map((bucket) => bucket.net_minor));
  const lowest = Math.min(0, ...buckets.map((bucket) => bucket.net_minor));
  const span = highest - lowest || 1;
  const y = (value: number) => 12 + ((highest - value) / span) * 76;
  const x = (index: number) => buckets.length === 1 ? 50 : 12 + index * (76 / (buckets.length - 1));
  return <div className="trend-currency"><svg className="trend-chart" viewBox="0 0 100 100" role="img" aria-label={`${currency} monthly activity trend`}><title>{currency} monthly activity trend</title><path d={`M8 ${y(0)}H92`} /><g>{buckets.map((bucket, index) => <circle key={bucket.period_start} data-testid={`trend-point-${bucket.period_start}`} cx={x(index)} cy={y(bucket.net_minor)} r="5"><title>{`${bucket.period_start}: ${formatMoney(bucket.net_minor, bucket.currency)} net, ${bucket.transaction_count} entries`}</title></circle>)}</g></svg><ol className="trend-key">{buckets.map((bucket) => <li key={bucket.period_start}><time dateTime={bucket.period_start}>{new Intl.DateTimeFormat(undefined, { month: "short", year: "numeric" }).format(new Date(`${bucket.period_start}T00:00:00`))}</time><strong>{bucket.currency}</strong><span>{formatMoney(bucket.net_minor, bucket.currency)} net</span><small>{bucket.transaction_count} entries</small></li>)}</ol></div>;
}
