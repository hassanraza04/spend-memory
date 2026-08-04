import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RecurringView } from "./recurring-view";

describe("RecurringView", () => {
  it("shows the expected next date and candidate evidence", () => {
    render(<RecurringView flows={[]} recurring={[{ candidate_id: "r1", label: "Music", cadence: "monthly", status: "suggested", confidence: 0.88, evidence: { amount_minor: 999 }, transaction_ids: ["t1"], expected_next_start: "2026-09-02", expected_next_end: "2026-09-05" }]} />);

    expect(screen.getByText("Expected next: 2026-09-02 to 2026-09-05")).toBeTruthy();
    expect(screen.getByText("Suggested pattern")).toBeTruthy();
    expect(screen.getByText("amount_minor: 999")).toBeTruthy();
    expect(screen.getByText("Whole-record recurring evidence")).toBeTruthy();
  });

  it("shows a local error instead of claiming no patterns exist", () => {
    render(<RecurringView flows={[]} recurring={[]} loadError="Recurring data could not be loaded. The local record is not ready." />);

    expect(screen.getByText("Recurring data could not be loaded. The local record is not ready.")).toBeTruthy();
    expect(screen.queryByText("No recurring patterns match this scope.")).toBeNull();
  });
});
