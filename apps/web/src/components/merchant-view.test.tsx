import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MerchantView } from "./merchant-view";

const flows = [{ currency: "AED", sent_minor: 1200, received_minor: 300, net_minor: -900, transaction_count: 2 }];

describe("MerchantView", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("keeps confirmed and suggested merchant evidence distinct", () => {
    render(<MerchantView flows={flows} merchants={[
      { transaction_id: "1", merchant_id: "a", merchant_name: "Cafe North", status: "confirmed", confidence: 1, method: "manual", evidence: { descriptor: "CAFE NORTH", normalized_descriptor: "cafe north" } },
      { transaction_id: "2", merchant_id: null, merchant_name: "Cafe N.", status: "suggested", confidence: 0.72, method: "lexical", evidence: { descriptor: "CAFE N" } },
    ]} categories={[]} counterpartyLabel="Rina" />);

    expect(screen.getByText("Confirmed")).toBeTruthy();
    expect(screen.getByText("Suggested")).toBeTruthy();
    expect(screen.getByText("Current person or account: Rina")).toBeTruthy();
    expect(screen.getByText("Whole-record merchant and category evidence")).toBeTruthy();
    expect(screen.getByTestId("merchant-card-1").getAttribute("data-resolution-method")).toBe("manual");
    expect(screen.getByTestId("merchant-card-1").getAttribute("data-normalized-descriptor")).toBe("cafe north");
  });

  it("labels an unresolved merchant without calling it a suggestion", () => {
    render(<MerchantView flows={flows} merchants={[{ transaction_id: "1", merchant_id: null, merchant_name: null, status: "unresolved", confidence: 0, method: "none", evidence: {} }]} categories={[]} />);

    expect(screen.getByText("Unresolved")).toBeTruthy();
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

  it("rejects an overlong descriptor before saving", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(<MerchantView flows={flows} merchants={[{ transaction_id: "1", merchant_id: "merchant-1", merchant_name: "Cafe North", status: "suggested", confidence: 0.72, method: "lexical", evidence: {} }]} categories={[]} />);

    const input = screen.getByLabelText("Exact statement label for Cafe North");
    fireEvent.change(input, { target: { value: "x".repeat(501) } });
    fireEvent.click(screen.getByRole("button", { name: "Save correction for Cafe North" }));

    expect(input.getAttribute("maxlength")).toBe("500");
    expect(screen.getByText("Use 500 characters or fewer.")).toBeTruthy();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("shows a local loading error instead of an empty result", () => {
    render(<MerchantView flows={flows} merchants={[]} categories={[]} loadError="Merchant and category data could not be loaded. The local record is not ready." />);

    expect(screen.getByText("Merchant and category data could not be loaded. The local record is not ready.")).toBeTruthy();
    expect(screen.queryByText("No merchant evidence matches this scope.")).toBeNull();
  });
});
