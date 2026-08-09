import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

const stylesheet = readFileSync("src/app/globals.css", "utf8");

function luminance(hex: string): number {
  const channels = hex.match(/[a-f\d]{2}/gi)?.map((channel) => Number.parseInt(channel, 16) / 255) ?? [];
  const [red, green, blue] = channels.map((channel) => channel <= 0.03928 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4);
  return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
}

function token(name: string): string {
  return stylesheet.match(new RegExp(`--${name}:\\s*(#[a-fA-F\\d]{6})`))?.[1] ?? "";
}

describe("Personal Record tokens", () => {
  it("uses locally bundled open-source typefaces", () => {
    expect(stylesheet).toContain('@import "@fontsource-variable/geist";');
    expect(stylesheet).toContain('@import "@fontsource-variable/source-serif-4";');
  });

  it("styles the selected section from its accessible state", () => {
    expect(stylesheet).toContain('.section-strip a[aria-current="page"]');
    expect(stylesheet).not.toContain(".section-strip a:first-child");
  });

  it("keeps primary action text at WCAG AA contrast", () => {
    const action = luminance(token("action"));
    const ink = luminance(token("action-ink"));
    const ratio = (Math.max(action, ink) + 0.05) / (Math.min(action, ink) + 0.05);

    expect(ratio).toBeGreaterThanOrEqual(4.5);
  });
});
