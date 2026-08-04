import type { CurrencyFlow, ReviewCandidate } from "../lib/api";
import { LensSummary } from "./lens-summary";
import { EvidenceList, RecordChart } from "./chart";

export function ReviewView({ flows, review, loadError }: Readonly<{ flows: readonly CurrencyFlow[]; review: readonly ReviewCandidate[]; loadError?: string }>) {
  return <section className="record-view" aria-labelledby="review-title"><p className="eyebrow">Review</p><h1 id="review-title">A few things worth checking</h1><p className="intro">These are suggestions. Your original statement is never changed automatically.</p><p className="scope-note">Current selected-scope flow</p><LensSummary flows={flows} /><p className="scope-note">Whole-record review evidence</p><RecordChart title="Whole-record review evidence rows" values={review.map((candidate) => ({ label: candidate.kind === "duplicate" ? "Possible duplicate" : "Unusual activity", value: candidate.transaction_ids.length }))} />
    <div className="candidate-grid">{loadError ? <p className="empty-note" role="status">{loadError}</p> : review.length ? review.map((candidate) => <article className="candidate-card" key={candidate.candidate_id}><h2>{candidate.kind === "duplicate" ? "Possible duplicate" : "Unusual activity"}</h2><p><span className="status-badge suggested">Suggested</span> {Math.round(candidate.confidence * 100)}% confidence</p><h3>Evidence</h3><EvidenceList values={candidate.evidence} /></article>) : <p className="empty-note">No whole-record review evidence is available yet.</p>}</div>
  </section>;
}
