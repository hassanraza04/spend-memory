"use client";
/* eslint-disable no-unused-vars -- the base ESLint preset does not understand TypeScript callback parameter names. */

import { useEffect, useState } from "react";

import { ApiClientError, type Transaction } from "../lib/api";
import { formatMoney } from "../lib/format";

function sourceLocation(transaction: Transaction): string {
  const location = transaction.source.page ? `page ${transaction.source.page}` : transaction.source.row ? `row ${transaction.source.row}` : `entry ${transaction.source.ordinal}`;
  return `${transaction.source.document} · ${location}`;
}

export function SourcePanel({ transaction, onClose, onCorrectMerchant }: Readonly<{ transaction: Transaction; onClose: () => void; onCorrectMerchant?: (merchantId: string, descriptor: string) => Promise<void> }>) {
  const [correctionState, setCorrectionState] = useState<"ready" | "saving" | "saved" | "saved_unrefreshed" | "failed">("ready");
  useEffect(() => {
    const close = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [onClose]);

  async function correctMerchant() {
    if (!transaction.merchant_id || !onCorrectMerchant) return;
    setCorrectionState("saving");
    try {
      await onCorrectMerchant(transaction.merchant_id, transaction.description);
      setCorrectionState("saved");
    } catch (error) {
      setCorrectionState(error instanceof ApiClientError && error.code === "local_refresh_failed" ? "saved_unrefreshed" : "failed");
    }
  }

  return (
    <aside className="source-panel" aria-label="Source evidence">
      <div className="panel-heading"><div><p className="eyebrow">Source evidence</p><h2>{transaction.merchant ?? transaction.description}</h2></div><button className="close-button" type="button" onClick={onClose} aria-label="Close source evidence">Close</button></div>
      <dl className="evidence-list">
        <div><dt>Statement text</dt><dd>{transaction.description}</dd></div>
        <div><dt>Source</dt><dd>{sourceLocation(transaction)}</dd></div>
        <div><dt>Recorded amount</dt><dd>{transaction.direction === "debit" ? "Sent " : "Received "}{formatMoney(transaction.amount_minor, transaction.currency)}</dd></div>
        <div><dt>Resolution</dt><dd>{transaction.state}</dd></div>
        <div><dt>Extraction confidence</dt><dd>{Math.round(transaction.source.extraction_confidence * 100)}%</dd></div>
      </dl>
      <p className="source-text">{transaction.source.text}</p>
      {transaction.merchant_id && transaction.merchant && onCorrectMerchant && <div className="inline-correction"><button className="button secondary" type="button" disabled={correctionState === "saving"} onClick={() => void correctMerchant()}>Use this statement label for {transaction.merchant}</button><p className="save-status" aria-live="polite">{correctionState === "saved" ? "Merchant correction saved." : correctionState === "saved_unrefreshed" ? "The correction was saved, but local activity could not be refreshed." : correctionState === "failed" ? "The merchant correction could not be saved." : ""}</p></div>}
    </aside>
  );
}
