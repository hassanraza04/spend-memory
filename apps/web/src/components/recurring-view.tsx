import type { CurrencyFlow, RecurringCandidate } from "../lib/api";
import { LensSummary } from "./lens-summary";
import { EvidenceList, RecordChart } from "./chart";

export function RecurringView({ flows, recurring, loadError }: Readonly<{ flows: readonly CurrencyFlow[]; recurring: readonly RecurringCandidate[]; loadError?: string }>) {
  return <section className="record-view" aria-labelledby="patterns-title"><p className="eyebrow">Patterns</p><h1 id="patterns-title">The payments that keep coming back</h1><p className="scope-note">Current selected-scope flow</p><LensSummary flows={flows} /><p className="scope-note">Whole-record recurring evidence</p><RecordChart title="Whole-record recurring candidate evidence" values={recurring.map((candidate) => ({ label: candidate.label, value: candidate.cadence }))} />
    <div className="candidate-grid">{loadError ? <p className="empty-note" role="status">{loadError}</p> : recurring.length ? recurring.map((candidate) => <article className="candidate-card" key={candidate.candidate_id}><h2>{candidate.label}</h2><p><span className={`status-badge ${candidate.status}`}>{candidate.status === "confirmed" ? "Confirmed pattern" : "Suggested pattern"}</span> {candidate.cadence}</p><p className="expected-date">Expected next: {candidate.expected_next_start} to {candidate.expected_next_end}</p><EvidenceList values={candidate.evidence} /></article>) : <p className="empty-note">No whole-record recurring evidence is available yet.</p>}</div>
  </section>;
}
