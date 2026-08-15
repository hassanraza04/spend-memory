import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ComparisonView } from "./comparison-view";

describe("ComparisonView", () => {
  const accounts = [{ account: "Daily", currencies: ["AED", "USD"] }, { account: "Savings", currencies: ["PKR"] }];

  it("uses native context selects to change the comparison pair", () => {
    const onScopeChange = vi.fn();
    render(<ComparisonView accounts={accounts} account="Daily" currency="AED" hasWorkspace hasPreviousPeriod onScopeChange={onScopeChange} />);

    expect(screen.getByRole("option", { name: "Savings" })).toBeTruthy();
    expect(screen.getByRole("option", { name: "USD" })).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Account"), { target: { value: "Savings" } });
    fireEvent.change(screen.getByLabelText("Currency"), { target: { value: "USD" } });

    expect(onScopeChange).toHaveBeenNthCalledWith(1, { account: "Savings", currency: "PKR" });
    expect(onScopeChange).toHaveBeenNthCalledWith(2, { currency: "USD" });
  });

  it("shows a plain local empty state when there is no workspace", () => {
    render(<ComparisonView accounts={[]} hasWorkspace={false} hasPreviousPeriod={false} onScopeChange={vi.fn()} />);

    expect(screen.getByText("There is no local activity to compare yet.")).toBeTruthy();
    expect(screen.queryByLabelText("Account")).toBeNull();
  });

  it("prioritizes missing-previous-period guidance over the API error", () => {
    render(<ComparisonView accounts={accounts} account="Daily" currency="AED" hasWorkspace hasPreviousPeriod={false} loadError="Comparison could not be loaded. The selected periods cannot be compared." onScopeChange={vi.fn()} />);

    expect(screen.getByText("An earlier matching period is needed before this month can be compared.")).toBeTruthy();
    expect(screen.queryByText("Comparison could not be loaded. The selected periods cannot be compared.")).toBeNull();
  });

  it("renders exact server contributions and a text waterfall alternative", () => {
    render(<ComparisonView accounts={accounts} account="Daily" currency="AED" hasWorkspace hasPreviousPeriod onScopeChange={vi.fn()} comparison={{ before_net_amount_minor: -1000, after_net_amount_minor: -700, difference_net_amount_minor: 300, contribution_total_minor: 300, remainder_minor: 0, text: "Spending changed by AED 3.00.", contributions: [{ label: "Cafe North", amount_minor: 300, before_transaction_ids: ["a"], after_transaction_ids: ["b"] }], before_transaction_ids: ["a"], after_transaction_ids: ["b"] }} />);

    expect(screen.getAllByText("Cafe North")).toHaveLength(2);
    expect(screen.getByLabelText("Waterfall text alternative")).toBeTruthy();
    expect(screen.getAllByText((_, element) => element?.tagName === "TD" && element.textContent?.includes("3.00") === true)).toHaveLength(2);
  });

  it("shows the local comparison error instead of an unavailable placeholder", () => {
    render(<ComparisonView accounts={accounts} account="Daily" currency="AED" hasWorkspace hasPreviousPeriod onScopeChange={vi.fn()} loadError="Comparison could not be loaded. The selected periods cannot be compared." />);

    expect(screen.getByText("Comparison could not be loaded. The selected periods cannot be compared.")).toBeTruthy();
    expect(screen.queryByText("There is no exact comparison available for this scope yet.")).toBeNull();
  });
});
