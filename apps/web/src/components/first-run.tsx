"use client";

import { useRef, useState } from "react";

import { ApiClient } from "../lib/api";

type ImportState = "empty" | "loading" | "unsupported" | "partial" | "failed" | "ready" | "demo-loading" | "demo-ready";

const api = new ApiClient();

function supported(file: File): boolean {
  return /\.(csv|pdf)$/i.test(file.name) || ["text/csv", "application/pdf"].includes(file.type);
}

export function FirstRun() {
  const input = useRef<HTMLInputElement>(null);
  const [importState, setImportState] = useState<ImportState>("empty");

  async function importFile(file: File) {
    if (!supported(file)) {
      setImportState("unsupported");
      return;
    }
    setImportState("loading");
    try {
      const result = await api.importStatement(file);
      setImportState(result.transaction_count === 0 ? "partial" : "ready");
    } catch {
      setImportState("failed");
    }
  }

  async function startDemo() {
    setImportState("demo-loading");
    try {
      await api.resetDemo();
      setImportState("demo-ready");
    } catch {
      setImportState("failed");
    }
  }

  return (
    <section className="first-run" aria-labelledby="monthly-question" data-state={importState}>
      <p className="eyebrow">Your private record</p>
      <h1 id="monthly-question">What happened this month?</h1>
      <p className="intro">Start with a statement, or take a quiet look around with made-up records.</p>

      <div className="start-choices">
        <article className="start-choice primary-choice">
          <p className="choice-number">01</p>
          <h2>Bring in a statement</h2>
          <p>Your statements stay on this device.</p>
          <button className="button primary" type="button" onClick={() => input.current?.click()}>
            Import a statement
          </button>
          <input
            ref={input}
            className="visually-hidden"
            id="statement-file"
            type="file"
            accept=".csv,.pdf,text/csv,application/pdf"
            aria-label="Choose a CSV or PDF"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) void importFile(file);
              event.currentTarget.value = "";
            }}
          />
        </article>
        <article className="start-choice">
          <p className="choice-number">02</p>
          <h2>See how it feels</h2>
          <p>Explore synthetic demo data. It is clearly labelled and never mixes with your own records.</p>
          <button className="button secondary" type="button" onClick={() => void startDemo()} disabled={importState === "demo-loading"}>
            Explore the synthetic demo
          </button>
        </article>
      </div>

      <p className="import-status" aria-live="polite">
        {importState === "loading" && "Checking file, reading statement, and reconciling import."}
        {importState === "unsupported" && "Choose a CSV or PDF statement."}
        {importState === "partial" && "The statement was read, but no transactions could be reconciled."}
        {importState === "failed" && "We could not import that statement. Try another supported file."}
        {importState === "ready" && "Your record is ready to review."}
        {importState === "demo-loading" && "Preparing the synthetic demo."}
        {importState === "demo-ready" && "Synthetic demo data is ready. Clear it before importing personal data."}
      </p>
    </section>
  );
}
