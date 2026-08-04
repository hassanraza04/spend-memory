import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ReviewView } from "./review-view";

describe("ReviewView", () => {
  it("shows review evidence without presenting it as a confirmed fact", () => {
    render(<ReviewView flows={[]} review={[{ candidate_id: "d1", kind: "duplicate", status: "suggested", confidence: 0.91, evidence: { days_apart: 1 }, transaction_ids: ["t1", "t2"] }]} />);

    expect(screen.getAllByText("Possible duplicate")).toHaveLength(2);
    expect(screen.getByText("Evidence")).toBeTruthy();
    expect(screen.getByText("days_apart: 1")).toBeTruthy();
  });
});
