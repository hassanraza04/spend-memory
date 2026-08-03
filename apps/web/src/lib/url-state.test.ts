import { describe, expect, it } from "vitest";

import { toWorkspaceHref, workspaceStateFrom } from "./url-state";

describe("workspace URL state", () => {
  it("keeps active scope while switching views", () => {
    const state = workspaceStateFrom(
      new URLSearchParams("after=2026-08-01&before=2026-09-01&account=Current&currency=PKR&q=ali&counterparty=Ali&status=suggested&amount_min_minor=500&amount_max_minor=9000&sort=amount&order=asc&limit=25&offset=50&selected=11111111-1111-1111-1111-111111111111"),
    );

    expect(toWorkspaceHref(state, "people-places")).toBe(
      "?view=people-places&after=2026-08-01&before=2026-09-01&account=Current&currency=PKR&q=ali&counterparty=Ali&status=suggested&amount_min_minor=500&amount_max_minor=9000&sort=amount&order=asc&limit=25&offset=50&selected=11111111-1111-1111-1111-111111111111",
    );
  });
});
