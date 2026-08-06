import { describe, expect, it } from "vitest";

import { localApiOrigin } from "./api-origin";

describe("localApiOrigin", () => {
  it("allows the local API and Docker internal API origins", () => {
    expect(localApiOrigin("http://127.0.0.1:8000")).toBe("http://127.0.0.1:8000");
    expect(localApiOrigin("http://api:8000")).toBe("http://api:8000");
  });

  it("rejects a non-local API origin", () => {
    expect(() => localApiOrigin("https://example.com")).toThrow("local API origin");
  });
});
