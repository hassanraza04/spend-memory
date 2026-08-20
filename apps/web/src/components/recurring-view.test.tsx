import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RecurringView } from "./recurring-view";

describe("RecurringView", () => {
  it("shows scoped recurring evidence when candidates exist", () => {
    const candidate = { candidate_id: "r1", label: "Streambox", cadence: "monthly", status: "suggested", confidence: 0.88, currency: "AED", amount_min_minor: 999, amount_max_minor: 1099, observation_count: 4, evidence: { amount_minor: 999, descriptor: "PRIVATE STREAMBOX LABEL", group_key: "private|group" }, transaction_ids: ["t1"], expected_next_start: "2026-09-02", expected_next_end: "2026-09-05" };
    render(<RecurringView scope="2026-08-01 to 2026-09-01" recurring={[candidate]} />);

    expect(screen.getByText("Scope: 2026-08-01 to 2026-09-01")).toBeTruthy();
    expect(screen.getByText("Recurring candidates in this scope are based on your trusted local activity.")).toBeTruthy();
    expect(screen.getByText("Expected next: 2026-09-02 to 2026-09-05")).toBeTruthy();
    expect(screen.getByText("Suggested pattern")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Streambox" })).toBeTruthy();
    expect(screen.queryByText("streambox monthly")).toBeNull();
    expect(screen.getByText("4 observations")).toBeTruthy();
    expect(screen.getByText(/AED\s*9\.99 to AED\s*10\.99/)).toBeTruthy();
    expect(screen.queryByText(/amount_minor|descriptor|group_key|PRIVATE STREAMBOX LABEL|private\|group/)).toBeNull();
    expect(screen.queryByLabelText("Whole-record recurring candidate evidence")).toBeNull();
  });

  it("shows a local error instead of claiming no patterns exist", () => {
    render(<RecurringView scope="All local activity" recurring={[]} loadError="Recurring data could not be loaded. The local record is not ready." />);

    expect(screen.getByText("Recurring data could not be loaded. The local record is not ready.")).toBeTruthy();
    expect(screen.queryByText("No recurring patterns match this scope.")).toBeNull();
  });

  it("keeps an empty scoped result calm", () => {
    render(<RecurringView scope="April 2026" recurring={[]} />);

    expect(screen.getByText("No recurring patterns match this scope yet.")).toBeTruthy();
    expect(screen.queryByText("Expected next:")).toBeNull();
  });
});
