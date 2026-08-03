import type { WorkspaceLens } from "../lib/api";
import { formatMoney } from "../lib/format";
import { toWorkspaceHref, type WorkspaceState } from "../lib/url-state";
import { LensSummary } from "./lens-summary";

export function MonthOverview({ lens, state }: Readonly<{ lens: WorkspaceLens; state: WorkspaceState }>) {
  const scope = [state.after && state.before && `${state.after} to ${state.before}`, state.account && `Account: ${state.account}`, state.currency && `Currency: ${state.currency}`].filter(Boolean).join(" · ");
  return (
    <section className="month-overview" aria-labelledby="monthly-question">
      <p className="eyebrow">Your private record</p>
      <div className="overview-heading"><div><h1 id="monthly-question">What happened this month?</h1><p className="intro">Here is the exact trusted activity in your current scope.</p>{scope && <p className="scope-note">{scope}</p>}</div><a className="quiet-link" href={toWorkspaceHref(state, "compare")}>Compare these periods</a></div>
      <LensSummary flows={lens.lens} />
      {lens.trend.length > 0 && <ActivityTrend trend={lens.trend} />}
    </section>
  );
}

function ActivityTrend({ trend }: Readonly<{ trend: WorkspaceLens["trend"] }>) {
  return (
    <section className="activity-trend" aria-labelledby="activity-trend-title">
      <div><p className="eyebrow">Through time</p><h2 id="activity-trend-title">Monthly activity</h2></div>
      <svg className="trend-chart" viewBox="0 0 100 100" role="img" aria-label="Monthly activity trend">
        <title>Monthly activity trend</title><path d="M8 50H92" /><g>{trend.map((bucket, index) => <circle key={`${bucket.period_start}-${bucket.currency}`} cx={trend.length === 1 ? 50 : 12 + index * (76 / (trend.length - 1))} cy={bucket.net_minor < 0 ? 70 : 30} r="5"><title>{`${bucket.period_start}: ${formatMoney(bucket.net_minor, bucket.currency)} net, ${bucket.transaction_count} entries`}</title></circle>)}</g>
      </svg>
      <ol className="trend-key">{trend.map((bucket) => <li key={`${bucket.period_start}-${bucket.currency}`}><time dateTime={bucket.period_start}>{new Intl.DateTimeFormat(undefined, { month: "short", year: "numeric" }).format(new Date(`${bucket.period_start}T00:00:00`))}</time><strong>{bucket.currency}</strong><span>{formatMoney(bucket.net_minor, bucket.currency)} net</span><small>{bucket.transaction_count} entries</small></li>)}</ol>
    </section>
  );
}
