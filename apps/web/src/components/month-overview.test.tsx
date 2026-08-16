import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MonthOverview } from "./month-overview";

describe("MonthOverview", () => {
  it("answers the monthly question with server-provided flows and one trend", () => {
    render(
      <MonthOverview
        lens={{
          lens: [{ currency: "AED", sent_minor: 1200, received_minor: 200, net_minor: -1000, transaction_count: 2 }],
          trend: [{ period_start: "2026-08-01", currency: "AED", sent_minor: 1200, received_minor: 200, net_minor: -1000, transaction_count: 2 }],
        }}
        state={{ after: "2026-08-01", before: "2026-09-01" }}
        scope="2026-08-01 to 2026-09-01 · Direction: debit"
      />,
    );

    expect(screen.getByRole("heading", { name: "What happened this month?" })).toBeTruthy();
    expect(screen.getByText("Scope: 2026-08-01 to 2026-09-01 · Direction: debit")).toBeTruthy();
    expect(screen.getByRole("img", { name: "AED monthly activity trend" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Compare these periods" })).toBeTruthy();
  });

  it("draws different server-provided magnitudes at different positions within one currency", () => {
    render(
      <MonthOverview
        lens={{
          lens: [{ currency: "AED", sent_minor: 1000001, received_minor: 0, net_minor: -1000001, transaction_count: 2 }],
          trend: [
            { period_start: "2026-07-01", currency: "AED", sent_minor: 1, received_minor: 0, net_minor: -1, transaction_count: 1 },
            { period_start: "2026-08-01", currency: "AED", sent_minor: 1000000, received_minor: 0, net_minor: -1000000, transaction_count: 1 },
          ],
        }}
        state={{ after: "2026-07-01", before: "2026-09-01" }}
        scope="2026-07-01 to 2026-09-01"
      />,
    );

    expect(screen.getByTestId("trend-point-2026-07-01").getAttribute("cy")).not.toBe(screen.getByTestId("trend-point-2026-08-01").getAttribute("cy"));
    expect(screen.getByRole("img", { name: "AED monthly activity trend" })).toBeTruthy();
  });
});
