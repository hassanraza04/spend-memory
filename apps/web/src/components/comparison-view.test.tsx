import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ComparisonView } from "./comparison-view";

describe("ComparisonView", () => {
  it("renders exact server contributions and a text waterfall alternative", () => {
    render(<ComparisonView account="Daily" currency="AED" comparison={{ before_net_amount_minor: -1000, after_net_amount_minor: -700, difference_net_amount_minor: 300, contribution_total_minor: 300, remainder_minor: 0, text: "Spending changed by AED 3.00.", contributions: [{ label: "Cafe North", amount_minor: 300, before_transaction_ids: ["a"], after_transaction_ids: ["b"] }], before_transaction_ids: ["a"], after_transaction_ids: ["b"] }} />);

    expect(screen.getAllByText("Cafe North")).toHaveLength(2);
    expect(screen.getByLabelText("Waterfall text alternative")).toBeTruthy();
    expect(screen.getAllByText((_, element) => element?.tagName === "TD" && element.textContent?.includes("3.00") === true)).toHaveLength(2);
  });
});
