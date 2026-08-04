"use client";

import { useEffect, useState } from "react";

import { ApiClient, type TransactionScope } from "../lib/api";

const api = new ApiClient();
const confirmation = "DELETE LOCAL DATA";

export function DataView({ scope, onDeleted }: Readonly<{ scope: TransactionScope; onDeleted?: () => void }>) {
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const [status, setStatus] = useState<"ready" | "deleting" | "deleted" | "failed">("ready");
  useEffect(() => { const close = (event: KeyboardEvent) => { if (event.key === "Escape") setOpen(false); }; window.addEventListener("keydown", close); return () => window.removeEventListener("keydown", close); }, []);
  async function remove() { if (typed !== confirmation) return; setStatus("deleting"); try { await api.deleteLocalData(); setStatus("deleted"); setOpen(false); onDeleted?.(); } catch { setStatus("failed"); } }
  return <section className="record-view" aria-labelledby="data-title"><p className="eyebrow">Data</p><h1 id="data-title">Your record stays here</h1><p className="intro">Exports and imports stay on this device. No upload is sent to a hosted service.</p><a className="button secondary" href={api.transactionsExportUrl(scope)}>Export current CSV</a><section className="danger-zone"><h2>Remove this local record</h2><p>This permanently removes the local database and imported files from this computer.</p><button className="button danger" type="button" onClick={() => { setTyped(""); setOpen(true); }}>Delete local data</button></section>{open && <div className="confirmation-dialog" role="dialog" aria-modal="true" aria-label="Delete local data"><div><h2>Delete local data</h2><p>Type the exact phrase to continue. This cannot be undone.</p><label>Type DELETE LOCAL DATA<input aria-label="Type DELETE LOCAL DATA" value={typed} onChange={(event) => setTyped(event.target.value)} /></label><div className="dialog-actions"><button className="button secondary" type="button" onClick={() => setOpen(false)}>Cancel</button><button className="button danger" type="button" disabled={typed !== confirmation || status === "deleting"} onClick={() => void remove()}>Permanently delete local data</button></div></div></div>}{status === "deleted" && <p className="save-status" role="status">Local data deleted.</p>}{status === "failed" && <p className="save-status" role="status">Local data could not be deleted.</p>}</section>;
}
