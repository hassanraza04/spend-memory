import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LensSummary } from "./lens-summary";

describe("LensSummary", () => {
  it("keeps sent, received, and net values separate for each currency", () => {
    render(
      <LensSummary
        flows={[
          { currency: "AED", sent_minor: 1200, received_minor: 200, net_minor: -1000, transaction_count: 2 },
          { currency: "PKR", sent_minor: 5000, received_minor: 0, net_minor: -5000, transaction_count: 1 },
        ]}
      />,
    );

    expect(screen.getByText("AED")).toBeTruthy();
    expect(screen.getByText("PKR")).toBeTruthy();
    expect(screen.getByLabelText("AED flow")).toBeTruthy();
    expect(screen.getByLabelText("PKR flow")).toBeTruthy();
    expect(screen.getAllByText("Sent")).toHaveLength(2);
    expect(screen.getAllByText("Received")).toHaveLength(2);
    expect(screen.getAllByText("Net flow")).toHaveLength(2);
    expect(screen.getByText(/AED\s+12\.00/)).toBeTruthy();
    expect(screen.getByText(/-AED\s+10\.00/)).toBeTruthy();
    expect(screen.getByText(/^PKR\s+5,000$/)).toBeTruthy();
  });
});
