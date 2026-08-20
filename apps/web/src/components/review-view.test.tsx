import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ReviewView } from "./review-view";

describe("ReviewView", () => {
  it("shows review evidence without presenting it as a confirmed fact", () => {
    const candidate = { candidate_id: "d1", kind: "duplicate" as const, status: "suggested", confidence: 0.91, currency: "AED", amount_minor: 12500, observation_count: 2, date_distance_days: 1, evidence: { merchant_key: "descriptor:PRIVATE", amount_minor: 12500, date_distance_days: 1 }, transaction_ids: ["t1", "t2"] };
    render(<ReviewView review={[candidate]} />);

    expect(screen.getByText(/Only suggestions with matching local evidence appear here/)).toBeTruthy();
    expect(screen.getByText("Possible duplicate")).toBeTruthy();
    expect(screen.getByText(/AED\s*125\.00/)).toBeTruthy();
    expect(screen.getByText("2 observations")).toBeTruthy();
    expect(screen.getByText("1 day apart")).toBeTruthy();
    expect(screen.queryByText(/merchant_key|descriptor:PRIVATE|amount_minor|date_distance_days/)).toBeNull();
  });

  it("shows a local error instead of claiming nothing needs review", () => {
    render(<ReviewView review={[]} loadError="Review data could not be loaded. The local record is not ready." />);

    expect(screen.getByText("Review data could not be loaded. The local record is not ready.")).toBeTruthy();
    expect(screen.queryByText("Nothing needs review in this scope.")).toBeNull();
  });

  it("uses an intentional empty state when there is no review work", () => {
    render(<ReviewView review={[]} />);

    expect(screen.getByText("Nothing needs review in this scope.")).toBeTruthy();
  });
});
