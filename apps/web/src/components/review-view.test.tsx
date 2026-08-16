import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ReviewView } from "./review-view";

describe("ReviewView", () => {
  it("shows review evidence without presenting it as a confirmed fact", () => {
    render(<ReviewView review={[{ candidate_id: "d1", kind: "duplicate", status: "suggested", confidence: 0.91, evidence: { days_apart: 1 }, transaction_ids: ["t1", "t2"] }]} />);

    expect(screen.getByText(/Only suggestions with matching local evidence appear here/)).toBeTruthy();
    expect(screen.getByText("Possible duplicate")).toBeTruthy();
    expect(screen.getByText("Evidence")).toBeTruthy();
    expect(screen.getByText("days_apart: 1")).toBeTruthy();
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
