"use client";

import { useState } from "react";

import { ApiClient, type Category, type CurrencyFlow, type MerchantEvidence } from "../lib/api";
import { formatMoney } from "../lib/format";
import { LensSummary } from "./lens-summary";
import { EvidenceList, RecordChart } from "./chart";

const api = new ApiClient();

function MerchantCard({ merchant }: Readonly<{ merchant: MerchantEvidence }>) {
  const [descriptor, setDescriptor] = useState("");
  const [state, setState] = useState<"ready" | "invalid" | "saving" | "saved" | "failed">("ready");
  const canCorrect = Boolean(merchant.merchant_id);
  async function save() {
    if (!descriptor.trim()) { setState("invalid"); return; }
    if (!merchant.merchant_id) return;
    setState("saving");
    try { await api.correctMerchant(merchant.merchant_id, descriptor.trim()); setState("saved"); } catch { setState("failed"); }
  }
  return <article className="candidate-card"><div className="candidate-heading"><div><h3>{merchant.merchant_name ?? "Unresolved statement label"}</h3><p><span className={`status-badge ${merchant.status}`}>{merchant.status === "confirmed" ? "Confirmed" : "Suggested"}</span> {Math.round(merchant.confidence * 100)}% confidence</p></div></div><EvidenceList values={merchant.evidence} />{canCorrect && <div className="inline-correction"><label>Exact statement label for {merchant.merchant_name}<input aria-label={`Exact statement label for ${merchant.merchant_name}`} value={descriptor} onChange={(event) => { setDescriptor(event.target.value); setState("ready"); }} /></label><button className="button secondary" type="button" disabled={state === "saving"} onClick={() => void save()}>Save correction for {merchant.merchant_name}</button>{state === "invalid" && <p role="status">Enter the exact statement label before saving.</p>}{state === "saved" && <p role="status">Saved.</p>}{state === "failed" && <p role="status">Could not save the correction.</p>}</div>}</article>;
}

export function MerchantView({ flows, merchants, categories, counterpartyLabel }: Readonly<{ flows: readonly CurrencyFlow[]; merchants: readonly MerchantEvidence[]; categories: readonly Category[]; counterpartyLabel?: string }>) {
  return <section className="record-view" aria-labelledby="people-title"><p className="eyebrow">People and places</p><h1 id="people-title">The names behind your activity</h1><p className="intro">Confirmed labels stay distinct from suggestions until you choose to correct them.</p>{counterpartyLabel && <p className="scope-note">Current person or account: {counterpartyLabel}</p>}<LensSummary flows={flows} /><RecordChart title="Category totals in the current scope" values={categories.flatMap((category) => category.lens.map((flow) => ({ label: `${category.label} (${flow.currency})`, value: formatMoney(flow.sent_minor, flow.currency) })))} />
    <div className="candidate-grid">{merchants.length ? merchants.map((merchant) => <MerchantCard key={merchant.transaction_id} merchant={merchant} />) : <p className="empty-note">No merchant evidence matches this scope.</p>}</div>
  </section>;
}
