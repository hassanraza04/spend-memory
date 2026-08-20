import type { ReviewCandidate } from "../lib/api";
import { formatMoney } from "../lib/format";

export function ReviewView({ review, loadError }: Readonly<{ review: readonly ReviewCandidate[]; loadError?: string }>) {
  return <section className="record-view" aria-labelledby="review-title"><p className="eyebrow">Review</p><h1 id="review-title">A few things worth checking</h1><p className="intro">Only suggestions with matching local evidence appear here. Your original statement is never changed automatically.</p>
    {loadError ? <p className="empty-note" role="status">{loadError}</p> : review.length ? <div className="candidate-grid">{review.map((candidate) => <article className="candidate-card" key={candidate.candidate_id}><h2>{candidate.kind === "duplicate" ? "Possible duplicate" : "Unusual activity"}</h2><p><span className="status-badge suggested">Suggested</span></p><dl className="candidate-evidence"><div><dt>Amount</dt><dd>{formatMoney(candidate.amount_minor, candidate.currency)}</dd></div><div><dt>History</dt><dd>{candidate.observation_count} observations</dd></div>{candidate.date_distance_days !== null && <div><dt>Date distance</dt><dd>{candidate.date_distance_days} {candidate.date_distance_days === 1 ? "day" : "days"} apart</dd></div>}</dl></article>)}</div> : <p className="empty-note">Nothing needs review in this scope.</p>}
  </section>;
}
