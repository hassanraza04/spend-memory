import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiClient } from "./api";

describe("ApiClient", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("sends a chosen statement only to the local versioned import route", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          document_id: "11111111-1111-1111-1111-111111111111",
          run_id: "22222222-2222-2222-2222-222222222222",
          transaction_count: 2,
          was_already_imported: false,
        }),
        { status: 201 },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await new ApiClient().importStatement(new File(["date,amount"], "statement.csv", { type: "text/csv" }));

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/imports",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("uses the exact local-data confirmation when clearing demo records", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: "deleted" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await new ApiClient().deleteLocalData();

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/local-data",
      expect.objectContaining({ method: "DELETE", body: JSON.stringify({ confirmation: "DELETE LOCAL DATA" }) }),
    );
  });

  it("gets workspace context from the local versioned route", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      firstTransactionDate: "2026-01-01",
      lastTransactionDate: "2026-04-30",
      latestMonthStart: "2026-04-01",
      latestMonthEnd: "2026-05-01",
      accounts: [{ account: "Everyday account", currencies: ["AED"] }],
    }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(new ApiClient().getWorkspaceContext()).resolves.toEqual({
      firstTransactionDate: "2026-01-01",
      lastTransactionDate: "2026-04-30",
      latestMonthStart: "2026-04-01",
      latestMonthEnd: "2026-05-01",
      accounts: [{ account: "Everyday account", currencies: ["AED"] }],
    });

    expect(fetchMock).toHaveBeenCalledWith("/api/v1/workspace-context", undefined);
  });

  it("lists typed people and places with the shared query scope", async () => {
    const grouped = {
      items: [{
        key: "merchant:11111111-1111-1111-1111-111111111111",
        label: "MetroMart",
        kind: "place",
        status: "confirmed",
        transactionCount: 3,
        lastActivityDate: "2026-04-12",
        flows: [{ currency: "AED", sent_minor: 1200, received_minor: 0, net_minor: -1200, transaction_count: 3 }],
        recentTransactionIds: ["22222222-2222-2222-2222-222222222222"],
      }],
      limit: 50,
      offset: 0,
      total: 1,
    };
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(grouped), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await new ApiClient().listPeoplePlaces({
      after: "2026-04-01",
      before: "2026-05-01",
      account: "Everyday",
      currency: "AED",
      direction: "debit",
      query: "metro",
    });

    expect(result).toEqual(grouped);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/people-places?after=2026-04-01&before=2026-05-01&account=Everyday&currency=AED&direction=debit&query=metro",
      undefined,
    );
  });
});
