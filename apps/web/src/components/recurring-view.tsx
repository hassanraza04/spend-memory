import type { RecurringCandidate } from "../lib/api";
import { EvidenceList } from "./chart";

export function RecurringView({ scope, recurring, loadError }: Readonly<{ scope: string; recurring: readonly RecurringCandidate[]; loadError?: string }>) {
  return <section className="record-view" aria-labelledby="patterns-title"><p className="eyebrow">Patterns</p><h1 id="patterns-title">The payments that keep coming back</h1><p className="scope-note">Scope: {scope}</p><p className="intro">Recurring candidates in this scope are based on your trusted local activity.</p>
    {loadError ? <p className="empty-note" role="status">{loadError}</p> : recurring.length ? <div className="candidate-grid">{recurring.map((candidate) => <article className="candidate-card" key={candidate.candidate_id}><h2>{candidate.label}</h2><p><span className={`status-badge ${candidate.status}`}>{candidate.status === "confirmed" ? "Confirmed pattern" : "Suggested pattern"}</span> {candidate.cadence}</p><p className="expected-date">Expected next: {candidate.expected_next_start} to {candidate.expected_next_end}</p><EvidenceList values={candidate.evidence} /></article>)}</div> : <p className="empty-note">No recurring patterns match this scope yet.</p>}
  </section>;
}
