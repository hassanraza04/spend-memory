import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApiClientError } from "../lib/api";
import { SourcePanel } from "./source-panel";

const transaction = {
  transaction_id: "00000000-0000-0000-0000-000000000001",
  transaction_date: "2026-08-02",
  account: "Daily",
  description: "Rina lunch",
  currency: "AED",
  amount_minor: 1200,
  direction: "debit" as const,
  merchant_id: "00000000-0000-0000-0000-000000000010",
  merchant: "Cafe North",
  category: "Meals",
  counterparty: "Rina",
  state: "confirmed",
  source: { document: "august.csv", ordinal: 7, page: null, row: 14, text: "Rina lunch", extraction_confidence: 0.98 },
};

describe("SourcePanel", () => {
  it("shows source evidence and closes with Escape", () => {
    const onClose = vi.fn();
    render(
      <SourcePanel
        transaction={transaction}
        onClose={onClose}
      />,
    );

    expect(screen.getByRole("complementary", { name: "Source evidence" })).toBeTruthy();
    expect(screen.getByText("august.csv · row 14")).toBeTruthy();
    expect(screen.getAllByText("Rina lunch")).toHaveLength(2);
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("clears the previous correction status when the transaction changes", async () => {
    const onCorrectMerchant = vi.fn().mockResolvedValue(undefined);
    const { rerender } = render(<SourcePanel key={transaction.transaction_id} transaction={transaction} onClose={vi.fn()} onCorrectMerchant={onCorrectMerchant} />);

    fireEvent.click(screen.getByRole("button", { name: "Use this statement label for Cafe North" }));
    expect(await screen.findByText("Merchant correction saved.")).toBeTruthy();

    const nextTransaction = { ...transaction, transaction_id: "00000000-0000-0000-0000-000000000002", description: "ORBIT FUEL 1092", merchant: "Orbit Fuel" };
    rerender(<SourcePanel key={nextTransaction.transaction_id} transaction={nextTransaction} onClose={vi.fn()} onCorrectMerchant={onCorrectMerchant} />);

    expect(screen.queryByText("Merchant correction saved.")).toBeNull();
  });

  it("reports a saved alias separately when only local refresh failed", async () => {
    const onCorrectMerchant = vi.fn().mockRejectedValue(new ApiClientError(
      "local_refresh_failed",
      "The correction was saved, but local activity could not be refreshed.",
    ));
    render(<SourcePanel transaction={transaction} onClose={vi.fn()} onCorrectMerchant={onCorrectMerchant} />);

    fireEvent.click(screen.getByRole("button", { name: "Use this statement label for Cafe North" }));

    expect(await screen.findByText("The correction was saved, but local activity could not be refreshed.")).toBeTruthy();
    expect(screen.queryByText("The merchant correction could not be saved.")).toBeNull();
  });

  it("reports a correction that was not saved", async () => {
    const onCorrectMerchant = vi.fn().mockRejectedValue(new ApiClientError(
      "request_failed",
      "The local request could not be completed.",
    ));
    render(<SourcePanel transaction={transaction} onClose={vi.fn()} onCorrectMerchant={onCorrectMerchant} />);

    fireEvent.click(screen.getByRole("button", { name: "Use this statement label for Cafe North" }));

    expect(await screen.findByText("The merchant correction could not be saved.")).toBeTruthy();
    expect(screen.queryByText("The correction was saved, but local activity could not be refreshed.")).toBeNull();
  });
});
