"use client";

import type { ReactNode } from "react";

import { toWorkspaceHref, workspaceStateFrom, type WorkspaceView } from "../lib/url-state";
import { ThemeToggle } from "./theme-toggle";

const sections: readonly [WorkspaceView, string][] = [
  ["this-month", "This month"],
  ["all-activity", "All activity"],
  ["people-places", "People & places"],
  ["patterns", "Patterns"],
  ["compare", "Compare"],
  ["data", "Data"],
];

export function AppShell({ children }: Readonly<{ children: ReactNode }>) {
  const state = typeof window === "undefined" ? {} : workspaceStateFrom(new URLSearchParams(window.location.search));

  return (
    <div className="app-shell">
      <header className="masthead">
        <a className="wordmark" href={toWorkspaceHref(state, "this-month")} aria-label="Spend Memory home">
          <span>Spend</span> Memory
        </a>
        <ThemeToggle />
      </header>
      <nav className="section-strip" aria-label="Workspace sections">
        {sections.map(([view, label]) => (
          <a key={view} href={toWorkspaceHref(state, view)}>
            {label}
          </a>
        ))}
      </nav>
      <main className="workspace">{children}</main>
    </div>
  );
}
