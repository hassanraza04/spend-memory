"use client";

import { useState } from "react";

import { ApiClient, type CurrencyFlow } from "../lib/api";
import { LensSummary } from "./lens-summary";

const api = new ApiClient();

export function CounterpartyEditor({ transactionIds, descriptor, onSaved }: Readonly<{ transactionIds: string[]; descriptor: string; onSaved?: () => void }>) {
  const [label, setLabel] = useState("");
  const [counterparty, setCounterparty] = useState<{ counterparty_id: string; label: string } | null>(null);
  const [lens, setLens] = useState<CurrencyFlow[]>([]);
  const [state, setState] = useState<"ready" | "saving" | "grouped" | "alias-saved" | "failed" | "created-not-grouped">("ready");

  async function group() {
    if (!label.trim() || !transactionIds.length) return;
    setState("saving");
    let labelCreated = false;
    try {
      const created = await api.createCounterparty(label.trim());
      labelCreated = true;
      setCounterparty(created);
      const result = await api.assignCounterparty(created.counterparty_id, transactionIds);
      setLens(result.lens);
      setState("grouped");
      onSaved?.();
    } catch { setState(labelCreated ? "created-not-grouped" : "failed"); }
  }

  async function confirmAlias() {
    if (!counterparty || !descriptor.trim()) return;
    setState("saving");
    try {
      await api.confirmCounterpartyAlias(counterparty.counterparty_id, descriptor);
      setState("alias-saved");
      onSaved?.();
    } catch { setState("failed"); }
  }

  return (
    <section className="counterparty-editor" aria-labelledby="counterparty-title">
      <p className="eyebrow">Group selected</p><h2 id="counterparty-title">Remember this person or account</h2>
      <p>Grouping is a local label. It does not change the original statement.</p>
      {counterparty ? state !== "created-not-grouped" && <><p className="save-status" aria-live="polite">{state === "alias-saved" ? "Exact alias confirmed." : `Grouped under ${counterparty.label}.`}</p><LensSummary flows={lens} />{descriptor && state !== "alias-saved" && <button className="button secondary" type="button" disabled={state === "saving"} onClick={() => void confirmAlias()}>Confirm exact alias</button>}</> : <div className="group-form"><label>Counterparty name<input aria-label="Counterparty name" value={label} onChange={(event) => setLabel(event.target.value)} /></label><button className="button primary" type="button" disabled={!label.trim() || state === "saving"} onClick={() => void group()}>Create and group</button></div>}
      {state === "created-not-grouped" && <p className="save-status" role="status">The label was created, but the selected entries were not grouped.</p>}
      {state === "failed" && <p className="save-status" role="status">We could not save that group.</p>}
    </section>
  );
}
