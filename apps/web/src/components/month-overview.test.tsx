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
      />,
    );

    expect(screen.getByRole("heading", { name: "What happened this month?" })).toBeTruthy();
    expect(screen.getByText("2026-08-01 to 2026-09-01")).toBeTruthy();
    expect(screen.getByRole("img", { name: "Monthly activity trend" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Compare these periods" })).toBeTruthy();
  });
});
