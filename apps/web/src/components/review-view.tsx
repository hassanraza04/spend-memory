import type { ReviewCandidate } from "../lib/api";
import { EvidenceList } from "./chart";

export function ReviewView({ review, loadError }: Readonly<{ review: readonly ReviewCandidate[]; loadError?: string }>) {
  return <section className="record-view" aria-labelledby="review-title"><p className="eyebrow">Review</p><h1 id="review-title">A few things worth checking</h1><p className="intro">Only suggestions with matching local evidence appear here. Your original statement is never changed automatically.</p>
    {loadError ? <p className="empty-note" role="status">{loadError}</p> : review.length ? <div className="candidate-grid">{review.map((candidate) => <article className="candidate-card" key={candidate.candidate_id}><h2>{candidate.kind === "duplicate" ? "Possible duplicate" : "Unusual activity"}</h2><p><span className="status-badge suggested">Suggested</span> {Math.round(candidate.confidence * 100)}% confidence</p><h3>Evidence</h3><EvidenceList values={candidate.evidence} /></article>)}</div> : <p className="empty-note">Nothing needs review in this scope.</p>}
  </section>;
}
