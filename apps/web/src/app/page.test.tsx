import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Page from "./page";

describe("home page", () => {
  it("renders the Spend Memory heading", () => {
    render(<Page />);

    expect(screen.getByRole("heading", { name: "Spend Memory" })).toBeTruthy();
  });
});
