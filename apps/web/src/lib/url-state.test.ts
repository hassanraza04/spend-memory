import { describe, expect, it } from "vitest";

import { mergeWorkspaceState, toWorkspaceHref, withDefaultMonthRange, workspaceStateFrom } from "./url-state";

describe("workspace URL state", () => {
  it("keeps active scope while switching views", () => {
    const state = workspaceStateFrom(
      new URLSearchParams("after=2026-08-01&before=2026-09-01&account=Current&currency=PKR&q=ali&counterparty=Ali&status=suggested&amount_min_minor=500&amount_max_minor=9000&sort=amount&order=asc&limit=25&offset=50&selected=11111111-1111-1111-1111-111111111111"),
    );

    expect(toWorkspaceHref(state, "people-places")).toBe(
      "?view=people-places&after=2026-08-01&before=2026-09-01&account=Current&currency=PKR&q=ali&counterparty=Ali&status=suggested&amount_min_minor=500&amount_max_minor=9000&sort=amount&order=asc&limit=25&offset=50&selected=11111111-1111-1111-1111-111111111111",
    );
  });

  it("keeps the active range while replacing a filter and clearing a selection", () => {
    expect(mergeWorkspaceState(
      { after: "2026-08-01", before: "2026-09-01", query: "Rina", selected: "row-1" },
      { query: "Ali", selected: undefined },
    )).toEqual({ after: "2026-08-01", before: "2026-09-01", query: "Ali" });
  });

  it("uses the current calendar month when a range is absent", () => {
    expect(withDefaultMonthRange({}, new Date(2026, 7, 3))).toEqual({ after: "2026-08-01", before: "2026-09-01" });
  });
});
