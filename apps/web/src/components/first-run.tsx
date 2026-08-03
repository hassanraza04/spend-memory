"use client";

import { useRef, useState } from "react";

import { ApiClient, ApiClientError } from "../lib/api";

type ImportState = "empty" | "loading" | "unsupported" | "partial" | "failed" | "ready" | "demo-loading" | "demo-ready" | "demo-blocked" | "demo-failed" | "clearing-demo" | "clear-failed";

const api = new ApiClient();
const demoWorkspaceKey = "spend-memory-demo-workspace";

function supported(file: File): boolean {
  return /\.(csv|pdf)$/i.test(file.name) || ["text/csv", "application/pdf"].includes(file.type);
}

function demoWorkspaceIsMarked(): boolean {
  try {
    return window.localStorage?.getItem(demoWorkspaceKey) === "true";
  } catch {
    return false;
  }
}

function markDemoWorkspace(isDemo: boolean) {
  try {
    if (isDemo) window.localStorage?.setItem(demoWorkspaceKey, "true");
    else window.localStorage?.removeItem(demoWorkspaceKey);
  } catch {
    // ponytail: keep the current-session safety gate when browser storage is unavailable.
  }
}

export function FirstRun() {
  const input = useRef<HTMLInputElement>(null);
  const [importState, setImportState] = useState<ImportState>(() => (
    typeof window !== "undefined" && demoWorkspaceIsMarked() ? "demo-ready" : "empty"
  ));
  const demoIsActive = ["demo-ready", "clearing-demo", "clear-failed"].includes(importState);

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
      markDemoWorkspace(true);
      setImportState("demo-ready");
    } catch (error) {
      setImportState(error instanceof ApiClientError && error.code === "non_demo_imports_present" ? "demo-blocked" : "demo-failed");
    }
  }

  async function clearDemo() {
    setImportState("clearing-demo");
    try {
      await api.deleteLocalData();
      markDemoWorkspace(false);
      setImportState("empty");
    } catch {
      setImportState("clear-failed");
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
          {demoIsActive ? (
            <button className="button primary" type="button" onClick={() => void clearDemo()} disabled={importState === "clearing-demo"}>
              Clear demo data
            </button>
          ) : (
            <>
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
            </>
          )}
        </article>
        <article className="start-choice">
          <p className="choice-number">02</p>
          <h2>See how it feels</h2>
          <p>Explore synthetic demo data. It is clearly labelled and never mixes with your own records.</p>
          <button className="button secondary" type="button" onClick={() => void startDemo()} disabled={importState === "demo-loading" || importState === "demo-ready" || importState === "clearing-demo"}>
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
        {importState === "demo-blocked" && "The demo cannot replace your imported records."}
        {importState === "demo-failed" && "We could not prepare the synthetic demo. Try again."}
        {importState === "clearing-demo" && "Clearing synthetic demo data."}
        {importState === "clear-failed" && "We could not clear demo data. Your personal data was not changed."}
      </p>
    </section>
  );
}
