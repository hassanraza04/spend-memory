import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MerchantView } from "./merchant-view";

const flows = [{ currency: "AED", sent_minor: 1200, received_minor: 300, net_minor: -900, transaction_count: 2 }];

describe("MerchantView", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("keeps confirmed and suggested merchant evidence distinct", () => {
    render(<MerchantView flows={flows} merchants={[
      { transaction_id: "1", merchant_id: "a", merchant_name: "Cafe North", status: "confirmed", confidence: 1, method: "manual", evidence: { descriptor: "CAFE NORTH" } },
      { transaction_id: "2", merchant_id: null, merchant_name: "Cafe N.", status: "suggested", confidence: 0.72, method: "lexical", evidence: { descriptor: "CAFE N" } },
    ]} categories={[]} counterpartyLabel="Rina" />);

    expect(screen.getByText("Confirmed")).toBeTruthy();
    expect(screen.getByText("Suggested")).toBeTruthy();
    expect(screen.getByText("Current person or account: Rina")).toBeTruthy();
  });

  it("validates and saves a merchant correction inline", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: "saved" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    render(<MerchantView flows={flows} merchants={[{ transaction_id: "1", merchant_id: "merchant-1", merchant_name: "Cafe North", status: "suggested", confidence: 0.72, method: "lexical", evidence: {} }]} categories={[]} />);

    fireEvent.click(screen.getByRole("button", { name: "Save correction for Cafe North" }));
    expect(screen.getByText("Enter the exact statement label before saving.")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Exact statement label for Cafe North"), { target: { value: "CAFE NORTH" } });
    fireEvent.click(screen.getByRole("button", { name: "Save correction for Cafe North" }));

    expect(await screen.findByText("Saved.")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/merchants/merchant-1", expect.objectContaining({ method: "PATCH" }));
  });
});
