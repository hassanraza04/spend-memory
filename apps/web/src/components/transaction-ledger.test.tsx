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
const emptyLens = { lens: [], trend: [] };

describe("TransactionLedger", () => {
  it("submits text and account filters, then keeps the selected row keyboard reachable", () => {
    const onScopeChange = vi.fn();
    const onSelect = vi.fn();
    render(
      <TransactionLedger
        page={{ items: rows, total: 1, limit: 50, offset: 0 }}
        lens={emptyLens}
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
        lens={emptyLens}
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

  it("does not open source evidence when Space toggles a grouping checkbox", () => {
    const onSelect = vi.fn();
    render(<TransactionLedger page={{ items: rows, total: 1, limit: 50, offset: 0 }} lens={emptyLens} state={{}} onScopeChange={vi.fn()} onSelect={onSelect} selectedForGrouping={[]} onToggleGrouping={vi.fn()} />);

    fireEvent.keyDown(screen.getByRole("checkbox", { name: "Group Rina lunch" }), { key: " " });
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("places the API result summary after the table and before the entry count", () => {
    const { container } = render(
      <TransactionLedger
        page={{ items: rows, total: 1, limit: 1, offset: 0 }}
        lens={{ lens: [{ currency: "AED", sent_minor: 1234, received_minor: 567, net_minor: -667, transaction_count: 2 }, { currency: "USD", sent_minor: 890, received_minor: 0, net_minor: -890, transaction_count: 1 }], trend: [] }}
        state={{}}
        onScopeChange={vi.fn()}
        onSelect={vi.fn()}
      />,
    );

    const summary = screen.getByRole("region", { name: "Result summary" });
    expect(summary.textContent).toMatch(/all matching entries/i);
    expect(summary.textContent).toContain("AED");
    expect(summary.textContent).toContain("AED 12.34");
    expect(summary.textContent).toContain("AED 5.67");
    expect(summary.textContent).toContain("-AED 6.67");
    expect(summary.textContent).toContain("USD");
    expect(summary.textContent).toContain("$8.90");
    expect(container.querySelector("table")?.compareDocumentPosition(summary)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(summary.compareDocumentPosition(screen.getByText("1 trusted entry"))).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
  });

  it("summarizes zero matching entries without fabricating money", () => {
    render(<TransactionLedger page={{ items: [], total: 0, limit: 50, offset: 0 }} lens={{ lens: [], trend: [] }} state={{}} onScopeChange={vi.fn()} onSelect={vi.fn()} />);

    const summary = screen.getByRole("region", { name: "Result summary" });
    expect(summary.textContent).toContain("0 matching entries");
    expect(summary.textContent).not.toMatch(/AED|USD|\d+\.\d{2}/);
  });

  it("keeps API lens totals when the visible search page is empty", () => {
    render(<TransactionLedger page={{ items: [], total: 0, limit: 1, offset: 1 }} lens={{ lens: [{ currency: "AED", sent_minor: 1234, received_minor: 0, net_minor: -1234, transaction_count: 2 }], trend: [] }} state={{}} onScopeChange={vi.fn()} onSelect={vi.fn()} />);

    const summary = screen.getByRole("region", { name: "Result summary" });
    expect(summary.textContent).toContain("AED 12.34");
    expect(summary.textContent).toContain("Entries2");
    expect(summary.textContent).not.toContain("0 matching entries");
  });
});
