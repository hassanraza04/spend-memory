import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { AppShell } from "./app-shell";

describe("AppShell", () => {
  const storage = new Map<string, string>();

  beforeEach(() => {
    storage.clear();
    window.history.replaceState({}, "", "/");
    Object.defineProperty(window, "localStorage", {
      configurable: true,
      value: {
        getItem: (key: string) => storage.get(key) ?? null,
        setItem: (key: string, value: string) => storage.set(key, value),
      },
    });
  });

  it("uses Personal Record by default and persists Night Desk", () => {
    const firstRender = render(<AppShell>Record</AppShell>);

    expect(document.documentElement.dataset.theme).toBe("personal-record");
    fireEvent.click(screen.getByRole("button", { name: "Use Night Desk" }));

    expect(document.documentElement.dataset.theme).toBe("night-desk");
    expect(storage.get("spend-memory-theme")).toBe("night-desk");
    firstRender.unmount();

    render(<AppShell>Record</AppShell>);

    expect(document.documentElement.dataset.theme).toBe("night-desk");
  });

  it("provides a keyboard-reachable navigation strip", () => {
    render(<AppShell>Record</AppShell>);

    const navigation = screen.getByRole("navigation", { name: "Workspace sections" });
    const links = within(navigation).getAllByRole("link");

    expect(navigation).toBeTruthy();
    expect(links.map((link) => link.textContent)).toEqual([
      "This month",
      "All activity",
      "People & places",
      "Patterns",
      "Compare",
      "Data",
    ]);
    links[0].focus();
    expect(document.activeElement).toBe(links[0]);
  });

  it("marks the URL-selected view as the current section", () => {
    window.history.replaceState({}, "", "/?view=data");
    render(<AppShell>Record</AppShell>);

    expect(screen.getByRole("link", { name: "Data" }).getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("link", { name: "This month" }).getAttribute("aria-current")).toBeNull();
  });
});
