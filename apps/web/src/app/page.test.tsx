import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import Page from "./page";

describe("home page", () => {
  beforeEach(() => window.history.replaceState({}, "", "/"));
  afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

  it("opens with the monthly question and the first-run choices", () => {
    render(<Page />);

    expect(screen.getByRole("heading", { name: "What happened this month?" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Import a statement" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Explore the synthetic demo" })).toBeTruthy();
  });

  it("persists the default current-month range in the URL", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 7, 3));
    render(<Page />);

    expect(window.location.search).toContain("after=2026-08-01");
    expect(window.location.search).toContain("before=2026-09-01");
  });

  it("keeps an empty filtered result in the record instead of returning to first run", async () => {
    window.history.replaceState({}, "", "/?after=2026-08-01&before=2026-09-01");
    vi.stubGlobal("fetch", vi.fn((url) => Promise.resolve(new Response(JSON.stringify(
      String(url).includes("/lens") ? { lens: [], trend: [] } : String(url).includes("limit=1") ? { items: [{}], total: 1, limit: 1, offset: 0 } : { items: [], total: 0, limit: 50, offset: 0 },
    ), { status: 200 }))));

    render(<Page />);

    expect(await screen.findByText("No trusted activity matches this scope.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Import a statement" })).toBeNull();
  });

  it("restores URL-selected source evidence after loading its row", async () => {
    window.history.replaceState({}, "", "/?selected=00000000-0000-0000-0000-000000000001");
    const transaction = {
      transaction_id: "00000000-0000-0000-0000-000000000001", transaction_date: "2026-08-02", account: "Daily", description: "Rina lunch", currency: "AED", amount_minor: 1200, direction: "debit", merchant: "Cafe North", category: "Meals", counterparty: "Rina", state: "confirmed", source: { document: "august.csv", ordinal: 7, page: null, row: 14, text: "Rina lunch", extraction_confidence: 0.98 },
    };
    vi.stubGlobal("fetch", vi.fn((url) => Promise.resolve(new Response(JSON.stringify(
      String(url).includes("/lens") ? { lens: [{ currency: "AED", sent_minor: 1200, received_minor: 0, net_minor: -1200, transaction_count: 1 }], trend: [] } : { items: [transaction], total: 1, limit: 1, offset: 0 },
    ), { status: 200 }))));

    render(<Page />);

    expect(await screen.findByRole("complementary", { name: "Source evidence" })).toBeTruthy();
  });
});
