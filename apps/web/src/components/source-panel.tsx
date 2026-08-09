"use client";

import { useEffect } from "react";

import type { Transaction } from "../lib/api";
import { formatMoney } from "../lib/format";

function sourceLocation(transaction: Transaction): string {
  const location = transaction.source.page ? `page ${transaction.source.page}` : transaction.source.row ? `row ${transaction.source.row}` : `entry ${transaction.source.ordinal}`;
  return `${transaction.source.document} · ${location}`;
}

export function SourcePanel({ transaction, onClose }: Readonly<{ transaction: Transaction; onClose: () => void }>) {
  useEffect(() => {
    const close = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [onClose]);

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
    </aside>
  );
}
