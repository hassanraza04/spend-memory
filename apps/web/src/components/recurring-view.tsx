import type { CurrencyFlow, RecurringCandidate } from "../lib/api";
import { LensSummary } from "./lens-summary";
import { EvidenceList, RecordChart } from "./chart";

export function RecurringView({ flows, recurring }: Readonly<{ flows: readonly CurrencyFlow[]; recurring: readonly RecurringCandidate[] }>) {
  return <section className="record-view" aria-labelledby="patterns-title"><p className="eyebrow">Patterns</p><h1 id="patterns-title">The payments that keep coming back</h1><LensSummary flows={flows} /><RecordChart title="Recurring candidate evidence" values={recurring.map((candidate) => ({ label: candidate.label, value: candidate.cadence }))} />
    <div className="candidate-grid">{recurring.length ? recurring.map((candidate) => <article className="candidate-card" key={candidate.candidate_id}><h2>{candidate.label}</h2><p><span className={`status-badge ${candidate.status}`}>{candidate.status === "confirmed" ? "Confirmed pattern" : "Suggested pattern"}</span> {candidate.cadence}</p><p className="expected-date">Expected next: {candidate.expected_next_start} to {candidate.expected_next_end}</p><EvidenceList values={candidate.evidence} /></article>) : <p className="empty-note">No recurring patterns match this scope.</p>}</div>
  </section>;
}
