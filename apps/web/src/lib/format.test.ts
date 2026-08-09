import { describe, expect, it } from "vitest";

import { formatMoney } from "./format";

describe("formatMoney", () => {
  it("formats an API integer amount for display", () => {
    expect(formatMoney(12345, "USD")).toContain("123.45");
  });
});
