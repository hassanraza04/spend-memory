import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { FilterControls } from "./filter-controls";

describe("FilterControls", () => {
  it("sends date, amount, merchant, category, counterparty, and review filters to the server scope", () => {
    const onApply = vi.fn();
    render(<FilterControls state={{}} onApply={onApply} />);

    fireEvent.change(screen.getByLabelText("From date"), { target: { value: "2026-08-01" } });
    fireEvent.change(screen.getByLabelText("To date"), { target: { value: "2026-09-01" } });
    fireEvent.change(screen.getByLabelText("Minimum amount"), { target: { value: "500" } });
    fireEvent.change(screen.getByLabelText("Merchant"), { target: { value: "Cafe North" } });
    fireEvent.change(screen.getByLabelText("Category"), { target: { value: "Meals" } });
    fireEvent.change(screen.getByLabelText("Counterparty"), { target: { value: "Rina" } });
    fireEvent.change(screen.getByLabelText("Review state"), { target: { value: "suggested" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply filters" }));

    expect(onApply).toHaveBeenCalledWith(expect.objectContaining({
      after: "2026-08-01", before: "2026-09-01", amountMinMinor: "500", merchant: "Cafe North", category: "Meals", counterparty: "Rina", state: "suggested",
    }));
  });
});
