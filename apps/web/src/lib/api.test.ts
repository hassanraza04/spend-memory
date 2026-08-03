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
});
