import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { FilterControls } from "./filter-controls";

describe("FilterControls", () => {
  it("keeps every labelled activity control discoverable", () => {
    render(<FilterControls state={{}} onApply={vi.fn()} />);

    for (const name of ["Search activity", "Account", "Currency", "Direction", "Sort", "Order"]) {
      expect(screen.getByLabelText(name)).toBeTruthy();
    }
  });

  it("hides optional controls until the native disclosure is opened", () => {
    render(<FilterControls state={{}} onApply={vi.fn()} />);

    const summary = screen.getByText("More filters", { selector: "summary" });
    const disclosure = summary.closest("details")!;
    const optionalNames = ["From date", "To date", "Minimum amount", "Maximum amount", "Merchant", "Category", "Counterparty", "Review state"];
    const optionalControls = optionalNames.map((name) => screen.getByLabelText(name));
    expect(disclosure.open).toBe(false);
    for (const control of optionalControls) expect(control.closest("details")?.open).toBe(false);

    fireEvent.click(summary);

    expect(disclosure.open).toBe(true);
    for (const control of optionalControls) expect(control.closest("details")?.open).toBe(true);
  });

  it("submits the same complete workspace state patch", () => {
    const onApply = vi.fn();
    render(<FilterControls state={{ limit: "50", offset: "50", selected: "entry-1" }} onApply={onApply} />);

    fireEvent.change(screen.getByLabelText("Search activity"), { target: { value: "Rina" } });
    fireEvent.change(screen.getByLabelText("Account"), { target: { value: "Daily" } });
    fireEvent.change(screen.getByLabelText("Currency"), { target: { value: "aed" } });
    fireEvent.change(screen.getByLabelText("Direction"), { target: { value: "debit" } });
    fireEvent.change(screen.getByLabelText("Sort"), { target: { value: "amount" } });
    fireEvent.change(screen.getByLabelText("Order"), { target: { value: "asc" } });
    fireEvent.click(screen.getByText("More filters"));
    fireEvent.change(screen.getByLabelText("From date"), { target: { value: "2026-08-01" } });
    fireEvent.change(screen.getByLabelText("To date"), { target: { value: "2026-09-01" } });
    fireEvent.change(screen.getByLabelText("Minimum amount"), { target: { value: "500" } });
    fireEvent.change(screen.getByLabelText("Maximum amount"), { target: { value: "2500" } });
    fireEvent.change(screen.getByLabelText("Merchant"), { target: { value: "Cafe North" } });
    fireEvent.change(screen.getByLabelText("Category"), { target: { value: "Meals" } });
    fireEvent.change(screen.getByLabelText("Counterparty"), { target: { value: "Rina" } });
    fireEvent.change(screen.getByLabelText("Review state"), { target: { value: "suggested" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply filters" }));

    expect(onApply).toHaveBeenCalledWith({
      limit: "50", offset: undefined, selected: undefined, query: "Rina", account: "Daily", currency: "AED", direction: "debit", sort: "amount", order: "asc",
      after: "2026-08-01", before: "2026-09-01", amountMinMinor: "500", amountMaxMinor: "2500", merchant: "Cafe North", category: "Meals", counterparty: "Rina", state: "suggested",
    });
  });
});
