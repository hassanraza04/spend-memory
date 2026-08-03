import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TransactionLedger } from "./transaction-ledger";

const rows = [{
  transaction_id: "00000000-0000-0000-0000-000000000001",
  transaction_date: "2026-08-02",
  account: "Daily",
  description: "Rina lunch",
  currency: "AED",
  amount_minor: 1200,
  direction: "debit" as const,
  merchant: "Cafe North",
  category: "Meals",
  counterparty: "Rina",
  state: "confirmed",
  source: { document: "august.csv", ordinal: 7, page: null, row: 14, text: "Rina lunch", extraction_confidence: 0.98 },
}];

describe("TransactionLedger", () => {
  it("submits text and account filters, then keeps the selected row keyboard reachable", () => {
    const onScopeChange = vi.fn();
    const onSelect = vi.fn();
    render(
      <TransactionLedger
        page={{ items: rows, total: 1, limit: 50, offset: 0 }}
        state={{ after: "2026-08-01", before: "2026-09-01", sort: "date", order: "desc" }}
        onScopeChange={onScopeChange}
        onSelect={onSelect}
      />,
    );

    fireEvent.change(screen.getByLabelText("Search activity"), { target: { value: "Rina" } });
    fireEvent.change(screen.getByLabelText("Account"), { target: { value: "Daily" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply filters" }));
    expect(onScopeChange).toHaveBeenCalledWith(expect.objectContaining({ query: "Rina", account: "Daily" }));

    const row = screen.getByRole("row", { name: /Rina lunch/i });
    row.focus();
    fireEvent.keyDown(row, { key: "Enter" });
    expect(onSelect).toHaveBeenCalledWith(rows[0]);
  });

  it("lets a person choose transaction rows for a manual group", () => {
    const onToggleGrouping = vi.fn();
    render(
      <TransactionLedger
        page={{ items: rows, total: 1, limit: 50, offset: 0 }}
        state={{}}
        onScopeChange={vi.fn()}
        onSelect={vi.fn()}
        selectedForGrouping={[]}
        onToggleGrouping={onToggleGrouping}
      />,
    );

    fireEvent.click(screen.getByRole("checkbox", { name: "Group Rina lunch" }));
    expect(onToggleGrouping).toHaveBeenCalledWith(rows[0].transaction_id);
  });
});
