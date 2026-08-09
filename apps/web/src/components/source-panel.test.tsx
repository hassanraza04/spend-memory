import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SourcePanel } from "./source-panel";

describe("SourcePanel", () => {
  it("shows source evidence and closes with Escape", () => {
    const onClose = vi.fn();
    render(
      <SourcePanel
        transaction={{
          transaction_id: "00000000-0000-0000-0000-000000000001",
          transaction_date: "2026-08-02",
          account: "Daily",
          description: "Rina lunch",
          currency: "AED",
          amount_minor: 1200,
          direction: "debit",
          merchant: "Cafe North",
          category: "Meals",
          counterparty: "Rina",
          state: "confirmed",
          source: { document: "august.csv", ordinal: 7, page: null, row: 14, text: "Rina lunch", extraction_confidence: 0.98 },
        }}
        onClose={onClose}
      />,
    );

    expect(screen.getByRole("complementary", { name: "Source evidence" })).toBeTruthy();
    expect(screen.getByText("august.csv · row 14")).toBeTruthy();
    expect(screen.getAllByText("Rina lunch")).toHaveLength(2);
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();
  });
});
