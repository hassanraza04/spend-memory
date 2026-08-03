import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { FirstRun } from "./first-run";

describe("FirstRun", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("explains that statements stay on this device", () => {
    render(<FirstRun />);

    expect(screen.getByText("Your statements stay on this device.")).toBeTruthy();
  });

  it("offers an import beside a clearly synthetic demo", () => {
    render(<FirstRun />);

    expect(screen.getByRole("button", { name: "Import a statement" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Explore the synthetic demo" })).toBeTruthy();
  });

  it("explains when a chosen file is unsupported", () => {
    render(<FirstRun />);

    fireEvent.change(screen.getByLabelText("Choose a CSV or PDF"), {
      target: { files: [new File(["hello"], "notes.txt", { type: "text/plain" })] },
    });

    expect(screen.getByText("Choose a CSV or PDF statement.")).toBeTruthy();
  });

  it("describes a partial import without guessing a completion percentage", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            document_id: "11111111-1111-1111-1111-111111111111",
            run_id: "22222222-2222-2222-2222-222222222222",
            transaction_count: 0,
            was_already_imported: false,
          }),
          { status: 201 },
        ),
      ),
    );
    render(<FirstRun />);

    fireEvent.change(screen.getByLabelText("Choose a CSV or PDF"), {
      target: { files: [new File(["date,amount"], "statement.csv", { type: "text/csv" })] },
    });

    expect(await screen.findByText("The statement was read, but no transactions could be reconciled.")).toBeTruthy();
  });

  it("keeps import failures plain and actionable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", { status: 500 })));
    render(<FirstRun />);

    fireEvent.change(screen.getByLabelText("Choose a CSV or PDF"), {
      target: { files: [new File(["date,amount"], "statement.csv", { type: "text/csv" })] },
    });

    expect(await screen.findByText("We could not import that statement. Try another supported file.")).toBeTruthy();
  });
});
