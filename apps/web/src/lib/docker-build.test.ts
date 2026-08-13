import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

const dockerfile = readFileSync("Dockerfile", "utf8");

describe("web Docker build", () => {
  it("sets the internal API origin before building Next.js", () => {
    expect(dockerfile).toContain("ENV SPEND_MEMORY_API_URL=http://api:8000");
    expect(dockerfile.indexOf("ENV SPEND_MEMORY_API_URL=http://api:8000")).toBeLessThan(
      dockerfile.indexOf("RUN pnpm --dir apps/web build"),
    );
  });
});
