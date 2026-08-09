import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CounterpartyEditor } from "./counterparty-editor";

describe("CounterpartyEditor", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("creates, groups, and confirms an alias only after explicit actions", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ counterparty_id: "00000000-0000-0000-0000-000000000001", label: "Rina" }), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ counterparty_id: "00000000-0000-0000-0000-000000000001", label: "Rina", lens: [{ currency: "AED", sent_minor: 1200, received_minor: 200, net_minor: -1000, transaction_count: 2 }] }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: "saved" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    render(<CounterpartyEditor transactionIds={["00000000-0000-0000-0000-000000000007"]} descriptor="RINA A." />);

    expect(fetchMock).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText("Counterparty name"), { target: { value: "Rina" } });
    fireEvent.click(screen.getByRole("button", { name: "Create and group" }));
    expect(await screen.findByText("Grouped under Rina.")).toBeTruthy();
    expect(screen.getByLabelText("Currency-separated activity summary")).toBeTruthy();
    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/v1/counterparties", expect.anything());
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/v1/counterparties/00000000-0000-0000-0000-000000000001/transactions", expect.anything());

    fireEvent.click(screen.getByRole("button", { name: "Confirm exact alias" }));
    expect(await screen.findByText("Exact alias confirmed.")).toBeTruthy();
    expect(fetchMock).toHaveBeenNthCalledWith(3, "/api/v1/counterparties/00000000-0000-0000-0000-000000000001", expect.anything());
  });

  it("does not claim a failed group left nothing behind after its label was created", async () => {
    vi.stubGlobal("fetch", vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ counterparty_id: "00000000-0000-0000-0000-000000000001", label: "Rina" }), { status: 201 }))
      .mockResolvedValueOnce(new Response("", { status: 500 })));
    render(<CounterpartyEditor transactionIds={["00000000-0000-0000-0000-000000000007"]} descriptor="RINA A." />);

    fireEvent.change(screen.getByLabelText("Counterparty name"), { target: { value: "Rina" } });
    fireEvent.click(screen.getByRole("button", { name: "Create and group" }));

    expect(await screen.findByText("The label was created, but the selected entries were not grouped." )).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Create and group" })).toBeNull();
    expect(screen.queryByText("We could not save that group. Nothing was changed.")).toBeNull();
  });
});
