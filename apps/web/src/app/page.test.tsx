import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import Page from "./page";

describe("home page", () => {
  const storage = new Map<string, string>();

  beforeEach(() => {
    window.history.replaceState({}, "", "/");
    storage.clear();
    Object.defineProperty(window, "localStorage", {
      configurable: true,
      value: {
        getItem: (key: string) => storage.get(key) ?? null,
        setItem: (key: string, value: string) => storage.set(key, value),
        removeItem: (key: string) => storage.delete(key),
      },
    });
  });
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.useRealTimers(); });

  it("opens with the monthly question and the first-run choices", () => {
    render(<Page />);

    expect(screen.getByRole("heading", { name: "What happened this month?" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Import a statement" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Explore the synthetic demo" })).toBeTruthy();
  });

  it("loads the latest available month and replaces the URL once", async () => {
    const transaction = {
      transaction_id: "00000000-0000-0000-0000-000000000001", transaction_date: "2026-04-10", account: "Daily", description: "April activity", currency: "AED", amount_minor: 1200, direction: "debit", merchant: "MetroMart", category: "Groceries", counterparty: null, state: "confirmed", source: { document: "april.csv", ordinal: 1, page: null, row: 2, text: "April activity", extraction_confidence: 0.98 },
    };
    const requests: string[] = [];
    vi.stubGlobal("fetch", vi.fn((url) => {
      requests.push(String(url));
      return Promise.resolve(new Response(JSON.stringify(
        String(url).includes("/workspace-context")
          ? { firstTransactionDate: "2026-01-01", lastTransactionDate: "2026-04-10", latestMonthStart: "2026-04-01", latestMonthEnd: "2026-05-01", accounts: [{ account: "Daily", currencies: ["AED"] }] }
          : String(url).includes("/lens")
            ? { lens: [{ currency: "AED", sent_minor: 1200, received_minor: 0, net_minor: -1200, transaction_count: 1 }], trend: [] }
            : { items: [transaction], total: 1, limit: 50, offset: 0 },
      ), { status: 200 }));
    }));
    const replaceState = vi.spyOn(window.history, "replaceState");

    render(<Page />);

    expect(await screen.findByText("MetroMart")).toBeTruthy();
    expect(requests[0]).toBe("/api/v1/workspace-context");
    expect(requests).toContain("/api/v1/transactions?after=2026-04-01&before=2026-05-01");
    expect(window.location.search).toContain("after=2026-04-01");
    expect(window.location.search).toContain("before=2026-05-01");
    expect(replaceState).toHaveBeenCalledOnce();
  });

  it("loads a partial URL range without waiting for workspace context", async () => {
    window.history.replaceState({}, "", "/?after=2026-04-01");
    const transaction = {
      transaction_id: "00000000-0000-0000-0000-000000000002", transaction_date: "2026-04-10", account: "Daily", description: "Partial range activity", currency: "AED", amount_minor: 1200, direction: "debit", merchant: "MetroMart", category: "Groceries", counterparty: null, state: "confirmed", source: { document: "april.csv", ordinal: 1, page: null, row: 2, text: "Partial range activity", extraction_confidence: 0.98 },
    };
    const fetchMock = vi.fn((url: string | URL) => {
      if (String(url).includes("/workspace-context")) return new Promise<Response>(() => {});
      return Promise.resolve(new Response(JSON.stringify(
        String(url).includes("/lens")
          ? { lens: [{ currency: "AED", sent_minor: 1200, received_minor: 0, net_minor: -1200, transaction_count: 1 }], trend: [] }
          : { items: [transaction], total: 1, limit: 50, offset: 0 },
      ), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<Page />);

    expect(await screen.findByText("MetroMart")).toBeTruthy();
    expect(fetchMock.mock.calls.map(([url]) => String(url))).not.toContain("/api/v1/workspace-context");
  });

  it("refreshes activity after grouping without refreshing workspace context", async () => {
    window.history.replaceState({}, "", "/?after=2026-04-01&before=2026-05-01");
    const transaction = {
      transaction_id: "00000000-0000-0000-0000-000000000003", transaction_date: "2026-04-10", account: "Daily", description: "Group me", currency: "AED", amount_minor: 1200, direction: "debit", merchant: "MetroMart", category: "Groceries", counterparty: null, state: "confirmed", source: { document: "april.csv", ordinal: 1, page: null, row: 2, text: "Group me", extraction_confidence: 0.98 },
    };
    const activityRequests: string[] = [];
    const fetchMock = vi.fn((url: string | URL, init?: { method?: string }) => {
      const path = String(url);
      if (path.includes("/workspace-context")) return Promise.resolve(new Response(JSON.stringify({ firstTransactionDate: "2026-04-01", lastTransactionDate: "2026-04-10", latestMonthStart: "2026-04-01", latestMonthEnd: "2026-05-01", accounts: [{ account: "Daily", currencies: ["AED"] }] }), { status: 200 }));
      if (init?.method === "POST" && path.endsWith("/counterparties")) return Promise.resolve(new Response(JSON.stringify({ counterparty_id: "00000000-0000-0000-0000-000000000010", label: "Rina" }), { status: 201 }));
      if (init?.method === "POST" && path.includes("/counterparties/")) return Promise.resolve(new Response(JSON.stringify({ lens: [] }), { status: 200 }));
      if (path.includes("/transactions")) activityRequests.push(path);
      return Promise.resolve(new Response(JSON.stringify(
        path.includes("/lens") ? { lens: [], trend: [] } : { items: [transaction], total: 1, limit: 50, offset: 0 },
      ), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<Page />);

    await screen.findByText("MetroMart");
    fireEvent.click(screen.getByLabelText("Group MetroMart"));
    fireEvent.change(screen.getByLabelText("Counterparty name"), { target: { value: "Rina" } });
    fireEvent.click(screen.getByRole("button", { name: "Create and group" }));

    await waitFor(() => expect(activityRequests).toHaveLength(4));
    expect(fetchMock.mock.calls.map(([url]) => String(url)).filter((url) => url.includes("/workspace-context"))).toHaveLength(0);
  });

  it("reloads an explicit scope after demo reset without workspace context", async () => {
    window.history.replaceState({}, "", "/?after=2026-04-01&before=2026-05-01");
    let demoReady = false;
    const transaction = {
      transaction_id: "00000000-0000-0000-0000-000000000004", transaction_date: "2026-04-10", account: "Daily", description: "Reset demo activity", currency: "AED", amount_minor: 1200, direction: "debit", merchant: "MetroMart", category: "Groceries", counterparty: null, state: "confirmed", source: { document: "april.csv", ordinal: 1, page: null, row: 2, text: "Reset demo activity", extraction_confidence: 0.98 },
    };
    const fetchMock = vi.fn((url: string | URL, init?: { method?: string }) => {
      const path = String(url);
      if (path.includes("/workspace-context")) return new Promise<Response>(() => {});
      if (init?.method === "POST" && path.includes("/demo/reset")) { demoReady = true; return Promise.resolve(new Response(JSON.stringify({ status: "reset" }), { status: 200 })); }
      return Promise.resolve(new Response(JSON.stringify(
        path.includes("/lens") ? { lens: [], trend: [] } : path.includes("limit=1") ? { items: demoReady ? [transaction] : [], total: demoReady ? 1 : 0, limit: 1, offset: 0 } : { items: demoReady ? [transaction] : [], total: demoReady ? 1 : 0, limit: 50, offset: 0 },
      ), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<Page />);

    const demo = await screen.findByRole("button", { name: "Explore the synthetic demo" });
    fireEvent.click(demo);

    expect(await screen.findByText("MetroMart")).toBeTruthy();
    expect(window.location.search).toBe("?after=2026-04-01&before=2026-05-01");
    expect(fetchMock.mock.calls.map(([url]) => String(url))).not.toContain("/api/v1/workspace-context");
  });

  it("switches to the available demo period after resetting the demo", async () => {
    let demoReady = false;
    vi.stubGlobal("fetch", vi.fn((url: string | URL, init?: { method?: string }) => {
      if (init?.method === "POST" && String(url).includes("/demo/reset")) demoReady = true;
      return Promise.resolve(new Response(JSON.stringify(
        init?.method === "POST" && String(url).includes("/demo/reset")
          ? { status: "reset" }
          : String(url).includes("/workspace-context")
            ? { firstTransactionDate: demoReady ? "2026-01-01" : null, lastTransactionDate: demoReady ? "2026-01-31" : null, latestMonthStart: demoReady ? "2026-01-01" : null, latestMonthEnd: demoReady ? "2026-02-01" : null, accounts: demoReady ? [{ account: "Daily", currencies: ["AED"] }] : [] }
            : String(url).includes("/lens")
              ? { lens: [], trend: [] }
              : { items: [], total: demoReady ? 1 : 0, limit: 50, offset: 0 },
      ), { status: 200 }));
    }));

    render(<Page />);
    const demo = screen.getByRole("button", { name: "Explore the synthetic demo" });
    await waitFor(() => expect(demo).toHaveProperty("disabled", false));
    fireEvent.click(demo);

    await screen.findByText("Here is the exact trusted activity in your current scope.");
    expect(window.location.search).toContain("after=2026-01-01");
    expect(window.location.search).toContain("before=2026-02-01");
  });

  it("restores the synthetic demo period when a marked demo workspace reloads", async () => {
    window.localStorage.setItem("spend-memory-demo-workspace", "true");
    vi.stubGlobal("fetch", vi.fn((url) => Promise.resolve(new Response(JSON.stringify(
      String(url).includes("/workspace-context") ? { firstTransactionDate: "2026-01-01", lastTransactionDate: "2026-01-31", latestMonthStart: "2026-01-01", latestMonthEnd: "2026-02-01", accounts: [{ account: "Daily", currencies: ["AED"] }] } : String(url).includes("/lens") ? { lens: [], trend: [] } : String(url).includes("limit=1") ? { items: [{}], total: 1, limit: 1, offset: 0 } : { items: [], total: 0, limit: 50, offset: 0 },
    ), { status: 200 }))));

    render(<Page />);

    await screen.findByText("Here is the exact trusted activity in your current scope.");
    expect(window.location.search).toContain("after=2026-01-01");
    expect(window.location.search).toContain("before=2026-02-01");
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

  it("defaults comparison to the first valid context pair and requests the preceding period", async () => {
    window.history.replaceState({}, "", "/?view=compare&after=2026-04-01&before=2026-05-01");
    const requests: string[] = [];
    const replaceState = vi.spyOn(window.history, "replaceState");
    vi.stubGlobal("fetch", vi.fn((url) => {
      const path = String(url);
      requests.push(path);
      return Promise.resolve(new Response(JSON.stringify(
        path.includes("/workspace-context")
          ? { firstTransactionDate: "2026-03-15", lastTransactionDate: "2026-04-30", latestMonthStart: "2026-04-01", latestMonthEnd: "2026-05-01", accounts: [{ account: "Daily", currencies: ["AED", "USD"] }, { account: "Savings", currencies: ["AED"] }] }
          : path.includes("/comparisons")
            ? { before_net_amount_minor: -1000, after_net_amount_minor: -700, difference_net_amount_minor: 300, contribution_total_minor: 300, remainder_minor: 0, text: "Spending changed by AED 3.00.", contributions: [{ label: "Cafe North", amount_minor: 300, before_transaction_ids: ["a"], after_transaction_ids: ["b"] }], before_transaction_ids: ["a"], after_transaction_ids: ["b"] }
            : path.includes("/lens")
              ? { lens: [], trend: [] }
              : { items: [{}], total: 1, limit: 1, offset: 0 },
      ), { status: 200 }));
    }));

    render(<Page />);

    expect(await screen.findByText("Spending changed by AED 3.00.")).toBeTruthy();
    expect(window.location.search).toContain("account=Daily");
    expect(window.location.search).toContain("currency=AED");
    expect(replaceState).toHaveBeenCalledOnce();
    expect(requests.filter((path) => path.includes("/comparisons"))).toEqual([
      "/api/v1/comparisons?before_start=2026-03-01&before_end=2026-04-01&after_start=2026-04-01&after_end=2026-05-01&account=Daily&currency=AED",
    ]);
  });

  it("keeps equal-length comparison subtraction for a custom period", async () => {
    window.history.replaceState({}, "", "/?view=compare&after=2026-04-02&before=2026-05-02&account=Daily&currency=AED");
    const requests: string[] = [];
    vi.stubGlobal("fetch", vi.fn((url) => {
      const path = String(url);
      requests.push(path);
      return Promise.resolve(new Response(JSON.stringify(
        path.includes("/workspace-context")
          ? { firstTransactionDate: "2026-03-01", lastTransactionDate: "2026-05-01", latestMonthStart: "2026-05-01", latestMonthEnd: "2026-06-01", accounts: [{ account: "Daily", currencies: ["AED"] }] }
          : path.includes("/comparisons")
            ? { before_net_amount_minor: -1000, after_net_amount_minor: -700, difference_net_amount_minor: 300, contribution_total_minor: 300, remainder_minor: 0, text: "Custom range compared.", contributions: [], before_transaction_ids: ["a"], after_transaction_ids: ["b"] }
            : path.includes("/lens")
              ? { lens: [], trend: [] }
              : { items: [{}], total: 1, limit: 1, offset: 0 },
      ), { status: 200 }));
    }));

    render(<Page />);

    expect(await screen.findByText("Custom range compared.")).toBeTruthy();
    expect(requests).toContain("/api/v1/comparisons?before_start=2026-03-03&before_end=2026-04-02&after_start=2026-04-02&after_end=2026-05-02&account=Daily&currency=AED");
  });

  it("explains when the comparison endpoint finds no matching earlier period", async () => {
    window.history.replaceState({}, "", "/?view=compare&after=2026-04-01&before=2026-05-01&account=Daily&currency=AED");
    vi.stubGlobal("fetch", vi.fn((url) => Promise.resolve(new Response(JSON.stringify(
      String(url).includes("/workspace-context")
        ? { firstTransactionDate: "2026-01-01", lastTransactionDate: "2026-04-30", latestMonthStart: "2026-04-01", latestMonthEnd: "2026-05-01", accounts: [{ account: "Daily", currencies: ["AED"] }] }
        : String(url).includes("/comparisons")
          ? { error: { code: "comparison_unavailable", message: "The selected periods cannot be compared." } }
          : String(url).includes("/lens")
            ? { lens: [], trend: [] }
            : { items: [{}], total: 1, limit: 1, offset: 0 },
    ), { status: String(url).includes("/comparisons") ? 422 : 200 }))));

    render(<Page />);

    expect(await screen.findByText("An earlier matching period is needed before this month can be compared.")).toBeTruthy();
  });

  it("renders a search result summary from the API lens without totaling visible rows", async () => {
    window.history.replaceState({}, "", "/?q=MetroMart&after=2026-01-01&before=2026-02-01");
    const transaction = {
      transaction_id: "00000000-0000-0000-0000-000000000001", transaction_date: "2026-01-01", account: "Daily", description: "MetroMart POS", currency: "AED", amount_minor: 1200, direction: "debit", merchant: "MetroMart", category: "Groceries", counterparty: null, state: "confirmed", source: { document: "january.csv", ordinal: 1, page: null, row: 2, text: "MetroMart POS", extraction_confidence: 0.98 },
    };
    vi.stubGlobal("fetch", vi.fn((url) => Promise.resolve(new Response(JSON.stringify(
      String(url).includes("/search")
        ? { query: "MetroMart", items: [transaction], total: 3, limit: 50, offset: 0, lens: [{ currency: "AED", sent_minor: 1234, received_minor: 567, net_minor: -667, transaction_count: 2 }, { currency: "USD", sent_minor: 890, received_minor: 0, net_minor: -890, transaction_count: 1 }] }
        : { items: [transaction], total: 1, limit: 1, offset: 0 },
    ), { status: 200 }))));

    render(<Page />);

    const summary = await screen.findByRole("region", { name: "Result summary" });
    expect(summary.textContent).toContain("AED");
    expect(summary.textContent).toContain("USD");
    expect(summary.textContent).toContain("12.34");
    expect(summary.textContent).toContain("5.67");
    expect(summary.textContent).toContain("-AED 6.67");
    expect(summary.textContent).toContain("$8.90");
  });

  it("keeps a search lens summary when its visible page has no rows", async () => {
    window.history.replaceState({}, "", "/?q=MetroMart&after=2026-01-01&before=2026-02-01&limit=1&offset=2");
    vi.stubGlobal("fetch", vi.fn((url) => Promise.resolve(new Response(JSON.stringify(
      String(url).includes("/search")
        ? { query: "MetroMart", items: [], total: 2, limit: 1, offset: 2, lens: [{ currency: "AED", sent_minor: 1234, received_minor: 0, net_minor: -1234, transaction_count: 2 }] }
        : { items: [{}], total: 1, limit: 1, offset: 0 },
    ), { status: 200 }))));

    render(<Page />);

    const summary = await screen.findByRole("region", { name: "Result summary" });
    expect(summary.textContent).toContain("AED 12.34");
    expect(summary.textContent).toContain("Entries2");
    expect(summary.textContent).not.toContain("0 matching entries");
    expect(screen.getByText("2 trusted entries")).toBeTruthy();
  });

  it("saves a merchant correction from source detail and refreshes activity", async () => {
    window.history.replaceState({}, "", "/?view=all-activity&after=2026-04-01&before=2026-05-01");
    const transaction = {
      transaction_id: "00000000-0000-0000-0000-000000000041", transaction_date: "2026-04-10", account: "Daily", description: "CAFE NORTH POS 8841", currency: "AED", amount_minor: 1200, direction: "debit", merchant_id: "00000000-0000-0000-0000-000000000042", merchant: "Cafe North", category: "Dining", counterparty: null, state: "confirmed", source: { document: "april.csv", ordinal: 1, page: null, row: 2, text: "CAFE NORTH POS 8841", extraction_confidence: 0.98 },
    };
    let activityLoads = 0;
    const fetchMock = vi.fn((url: string | URL, init?: { method?: string }) => {
      const path = String(url);
      if (init?.method === "PATCH") return Promise.resolve(new Response(JSON.stringify({ status: "saved" }), { status: 200 }));
      if (path.includes("/lens")) return Promise.resolve(new Response(JSON.stringify({ lens: [], trend: [] }), { status: 200 }));
      if (path.includes("/transactions?after=")) activityLoads += 1;
      return Promise.resolve(new Response(JSON.stringify({ items: [transaction], total: 1, limit: 50, offset: 0 }), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<Page />);

    fireEvent.click(await screen.findByRole("row", { name: /Cafe North/ }));
    fireEvent.click(await screen.findByRole("button", { name: "Use this statement label for Cafe North" }));
    expect(await screen.findByText("Merchant correction saved.")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/merchants/00000000-0000-0000-0000-000000000042",
      expect.objectContaining({ method: "PATCH", body: JSON.stringify({ descriptor: "CAFE NORTH POS 8841" }) }),
    );
    await waitFor(() => expect(activityLoads).toBeGreaterThan(1));
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

  it("opens recurring patterns inside the retained record scope", async () => {
    window.history.replaceState({}, "", "/?view=patterns&after=2026-08-01&before=2026-09-01&direction=debit&sort=amount&order=desc&limit=25&offset=50");
    const requests: string[] = [];
    vi.stubGlobal("fetch", vi.fn((url) => {
      requests.push(String(url));
      return Promise.resolve(new Response(JSON.stringify(
      String(url).includes("/lens") ? { lens: [], trend: [] } : String(url).includes("/recurring") ? { items: [{ candidate_id: "r1", label: "Music", cadence: "monthly", status: "suggested", confidence: 0.9, evidence: {}, transaction_ids: ["t1"], expected_next_start: "2026-09-01", expected_next_end: "2026-09-03", currency: "AED", amount_min_minor: 999, amount_max_minor: 1099, observation_count: 4 }], total: 1, limit: 100, offset: 0 } : String(url).includes("/review") ? { items: [], total: 0, limit: 100, offset: 0 } : { items: [{}], total: 1, limit: 1, offset: 0 },
    ), { status: 200 }));
    }));

    render(<Page />);

    expect(await screen.findByRole("heading", { name: "The payments that keep coming back" })).toBeTruthy();
    expect(screen.getAllByText("Scope: 2026-08-01 to 2026-09-01 · Direction: debit")).toHaveLength(1);
    expect(await screen.findByText("Expected next: 2026-09-01 to 2026-09-03")).toBeTruthy();
    expect(requests).toContain("/api/v1/recurring?after=2026-08-01&before=2026-09-01&direction=debit");
    expect(requests).toContain("/api/v1/review?after=2026-08-01&before=2026-09-01&direction=debit");
    expect(requests.filter((path) => path.includes("/recurring") || path.includes("/review"))).not.toEqual(expect.arrayContaining([expect.stringMatching(/[?&](sort|order|limit|offset)=/)]));
  });

  it("uses the shared scope label for all activity", async () => {
    window.history.replaceState({}, "", "/?view=all-activity&after=2026-04-01&before=2026-05-01&account=Daily&currency=AED&direction=credit");
    const transaction = { transaction_id: "00000000-0000-0000-0000-000000000201", transaction_date: "2026-04-10", account: "Daily", description: "Salary", currency: "AED", amount_minor: 50000, direction: "credit", merchant: null, category: "Income", counterparty: null, state: "confirmed", source: { document: "april.csv", ordinal: 1, page: null, row: 2, text: "Salary", extraction_confidence: 1 } };
    vi.stubGlobal("fetch", vi.fn((url) => Promise.resolve(new Response(JSON.stringify(
      String(url).includes("/lens") ? { lens: [], trend: [] } : { items: [transaction], total: 1, limit: 1, offset: 0 },
    ), { status: 200 }))));

    render(<Page />);

    expect(await screen.findByRole("heading", { name: "All activity" })).toBeTruthy();
    expect(screen.getByText("Scope: 2026-04-01 to 2026-05-01 · Account: Daily · Currency: AED · Direction: credit")).toBeTruthy();
  });

  it("loads people and places with the exact current API scope", async () => {
    window.history.replaceState({}, "", "/?view=people-places&after=2026-04-01&before=2026-05-01&account=Daily&currency=AED&q=Coffee&merchant=MetroMart&category=Groceries&counterparty=Rina&state=unresolved&direction=debit&amount_min_minor=500&amount_max_minor=30000&sort=amount&order=desc&limit=25&offset=50&selected=00000000-0000-0000-0000-000000000099");
    const requests: string[] = [];
    vi.stubGlobal("fetch", vi.fn((url) => {
      const path = String(url);
      requests.push(path);
      return Promise.resolve(new Response(JSON.stringify(
        path.includes("/lens")
          ? { lens: [{ currency: "AED", sent_minor: 1200, received_minor: 0, net_minor: -1200, transaction_count: 1 }], trend: [] }
          : path.includes("/search")
            ? { query: "MetroMart", items: [], total: 2, limit: 25, offset: 50, lens: [{ currency: "AED", sent_minor: 25000, received_minor: 0, net_minor: -25000, transaction_count: 2 }] }
          : path.includes("/people-places")
            ? { items: [{ key: "merchant:metro", label: "MetroMart", kind: "place", status: "confirmed", transactionCount: 2, lastActivityDate: "2026-04-12", flows: [{ currency: "AED", sent_minor: 25000, received_minor: 0, net_minor: -25000, transaction_count: 2 }], recentTransactionIds: ["t2", "t1"] }], total: 1, limit: 50, offset: 0 }
            : path.includes("/transactions")
              ? { items: [], total: path.includes("limit=1") ? 1 : 0, limit: path.includes("limit=1") ? 1 : 50, offset: 0 }
            : { items: [{}], total: 1, limit: 1, offset: 0 },
      ), { status: 200 }));
    }));

    render(<Page />);

    expect(await screen.findByRole("heading", { name: "Places and merchants" })).toBeTruthy();
    expect(screen.getByText("Scope: 2026-04-01 to 2026-05-01 · Account: Daily · Currency: AED · Direction: debit")).toBeTruthy();
    expect(requests).toContain("/api/v1/people-places?after=2026-04-01&before=2026-05-01&account=Daily&currency=AED&direction=debit&amount_min_minor=500&amount_max_minor=30000&merchant=MetroMart&category=Groceries&counterparty=Rina&state=unresolved&query=Coffee");
    expect(requests.filter((path) => path.includes("/people-places"))).not.toEqual(expect.arrayContaining([expect.stringMatching(/[?&](sort|order|limit|offset)=/)]));
    expect(requests.some((path) => path.includes("/merchants"))).toBe(false);
    expect(requests.some((path) => path.includes("/categories"))).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "Show activity" }));
    expect(await screen.findByRole("heading", { name: "All activity" })).toBeTruthy();
    expect(window.location.search).toBe("?view=all-activity&after=2026-04-01&before=2026-05-01&account=Daily&currency=AED&merchant=MetroMart&category=Groceries&direction=debit&amount_min_minor=500&amount_max_minor=30000&sort=amount&order=desc&limit=25");
  });

  it("never opens selected source evidence in people and places", async () => {
    window.history.replaceState({}, "", "/?view=people-places&after=2026-04-01&before=2026-05-01&selected=00000000-0000-0000-0000-000000000099");
    const transaction = {
      transaction_id: "00000000-0000-0000-0000-000000000099", transaction_date: "2026-04-12", account: "Daily", description: "PRIVATE RESOLUTION LABEL", currency: "AED", amount_minor: 1200, direction: "debit", merchant: "MetroMart", category: "Groceries", counterparty: null, state: "confirmed_alias", source: { document: "private.csv", ordinal: 1, page: null, row: 2, text: "RAW PRIVATE SOURCE", extraction_confidence: 0.97 },
    };
    vi.stubGlobal("fetch", vi.fn((url) => Promise.resolve(new Response(JSON.stringify(
      String(url).includes("/lens")
        ? { lens: [{ currency: "AED", sent_minor: 1200, received_minor: 0, net_minor: -1200, transaction_count: 1 }], trend: [] }
        : String(url).includes("/people-places")
          ? { items: [], total: 0, limit: 50, offset: 0 }
          : { items: [transaction], total: 1, limit: 50, offset: 0 },
    ), { status: 200 }))));

    render(<Page />);

    expect(await screen.findByRole("heading", { name: "The names behind your activity" })).toBeTruthy();
    expect(screen.queryByRole("complementary", { name: "Source evidence" })).toBeNull();
    expect(screen.queryByText("RAW PRIVATE SOURCE")).toBeNull();
    expect(screen.queryByText("Extraction confidence")).toBeNull();
    expect(screen.queryByText("Resolution")).toBeNull();
  });

  it("keeps local data controls available while the record refreshes", () => {
    window.history.replaceState({}, "", "/?view=data");
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));

    render(<Page />);

    expect(screen.getByRole("link", { name: "Export current CSV" })).toBeTruthy();
  });

  it("returns to the first-run choice after local data is deleted", async () => {
    window.history.replaceState({}, "", "/?view=data");
    vi.stubGlobal("fetch", vi.fn((url: string | URL, init?: { method?: string }) => Promise.resolve(new Response(JSON.stringify(
      init?.method === "DELETE" ? { status: "deleted" } : String(url).includes("/lens") ? { lens: [], trend: [] } : { items: [], total: 1, limit: 1, offset: 0 },
    ), { status: 200 }))));

    render(<Page />);

    await screen.findByRole("link", { name: "Export current CSV" });
    fireEvent.click(screen.getByRole("button", { name: "Delete local data" }));
    fireEvent.change(screen.getByLabelText("Type DELETE LOCAL DATA"), { target: { value: "DELETE LOCAL DATA" } });
    fireEvent.click(screen.getByRole("button", { name: "Permanently delete local data" }));

    expect(await screen.findByRole("button", { name: "Import a statement" })).toBeTruthy();
  });
});
