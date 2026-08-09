"use client";

import { useSyncExternalStore, type MouseEvent, type ReactNode } from "react";

import { toWorkspaceHref, workspaceStateFrom, workspaceViewFrom, type WorkspaceView } from "../lib/url-state";
import { ThemeToggle } from "./theme-toggle";

const sections: readonly [WorkspaceView, string][] = [
  ["this-month", "This month"],
  ["all-activity", "All activity"],
  ["people-places", "People & places"],
  ["patterns", "Patterns"],
  ["compare", "Compare"],
  ["data", "Data"],
];

function keepLiveScope(event: MouseEvent<HTMLAnchorElement>, view: WorkspaceView) {
  event.currentTarget.setAttribute("href", toWorkspaceHref(workspaceStateFrom(new URLSearchParams(window.location.search)), view));
}

function subscribeToNothing() {
  return () => {};
}

function browserSearch() {
  return window.location.search;
}

function serverSearch() {
  return "";
}

function demoIsActive() {
  try {
    return window.localStorage?.getItem("spend-memory-demo-workspace") === "true";
  } catch {
    return false;
  }
}

export function AppShell({ children }: Readonly<{ children: ReactNode }>) {
  const params = new URLSearchParams(useSyncExternalStore(subscribeToNothing, browserSearch, serverSearch));
  const state = workspaceStateFrom(params);
  const activeView = workspaceViewFrom(params);

  return (
    <div className="app-shell">
      <header className="masthead">
        <a className="wordmark" href={toWorkspaceHref(state, "this-month")} aria-label="Spend Memory home" onClick={(event) => keepLiveScope(event, "this-month")}>
          <span>Spend</span> Memory
        </a>
        {typeof window !== "undefined" && demoIsActive() && <p className="demo-label">Synthetic demo</p>}
        <ThemeToggle />
      </header>
      <nav className="section-strip" aria-label="Workspace sections">
        {sections.map(([view, label]) => (
          <a key={view} href={toWorkspaceHref(state, view)} aria-current={activeView === view ? "page" : undefined} onClick={(event) => keepLiveScope(event, view)}>
            {label}
          </a>
        ))}
      </nav>
      <main className="workspace">{children}</main>
    </div>
  );
}
