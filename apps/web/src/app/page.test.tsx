import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Page from "./page";

describe("home page", () => {
  it("opens with the monthly question and the first-run choices", () => {
    render(<Page />);

    expect(screen.getByRole("heading", { name: "What happened this month?" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Import a statement" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Explore the synthetic demo" })).toBeTruthy();
  });
});
