import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { PeoplePlace } from "../lib/api";
import { MerchantView } from "./merchant-view";

const scopeFlows = [{ currency: "AED", sent_minor: 9999, received_minor: 0, net_minor: -9999, transaction_count: 9 }];

function group(overrides: Partial<PeoplePlace>): PeoplePlace {
  return {
    key: "merchant:cafe-north",
    label: "Cafe North",
    kind: "place",
    status: "confirmed",
    transactionCount: 2,
    lastActivityDate: "2026-04-18",
    flows: [{ currency: "AED", sent_minor: 1234, received_minor: 567, net_minor: -667, transaction_count: 2 }],
    recentTransactionIds: ["transaction-2", "transaction-1"],
    ...overrides,
  };
}

describe("MerchantView", () => {
  it("shows one repeated place group with exact server flows and no raw evidence", () => {
    const place = {
      ...group({}),
      descriptor: "CAFE NORTH POS",
      normalized_descriptor: "cafe north pos",
      original_label: "CAFE NORTH",
      method: "confirmed_alias",
      confidence: 0.97,
    };

    render(<MerchantView scope="April 2026 · Direction: debit" flows={scopeFlows} peoplePlaces={[place]} onShowActivity={vi.fn()} />);

    expect(screen.getByRole("heading", { name: "Places and merchants" })).toBeTruthy();
    expect(screen.getByText("Scope: April 2026 · Direction: debit")).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "People and transfers" })).toBeNull();
    expect(screen.queryByRole("heading", { name: "Needs review" })).toBeNull();
    const card = screen.getByRole("article", { name: "Cafe North" });
    expect(card.textContent).toContain("Confirmed");
    expect(card.textContent).toContain("2 transactions");
    expect(card.textContent).toContain("Last activity 2026-04-18");
    expect(card.textContent).toContain("AED\u00a012.34");
    expect(card.textContent).toContain("AED\u00a05.67");
    expect(card.textContent).toContain("-AED\u00a06.67");
    expect(card.textContent).not.toContain("CAFE NORTH POS");
    expect(card.textContent).not.toContain("cafe north pos");
    expect(card.textContent).not.toContain("CAFE NORTH");
    expect(card.textContent).not.toContain("confirmed_alias");
    expect(card.textContent).not.toContain("97% confidence");
  });

  it("shows a person group and applies its counterparty activity patch", () => {
    const onShowActivity = vi.fn();
    render(<MerchantView scope="All local activity" flows={scopeFlows} peoplePlaces={[group({
      key: "counterparty:rina",
      label: "Rina",
      kind: "person",
      transactionCount: 1,
      lastActivityDate: "2026-04-11",
      flows: [{ currency: "USD", sent_minor: 4200, received_minor: 1000, net_minor: -3200, transaction_count: 1 }],
    })]} onShowActivity={onShowActivity} />);

    expect(screen.getByRole("heading", { name: "People and transfers" })).toBeTruthy();
    const card = screen.getByRole("article", { name: "Rina" });
    expect(card.textContent).toContain("$42.00");
    expect(card.textContent).toContain("$10.00");
    expect(card.textContent).toContain("-$32.00");
    fireEvent.click(within(card).getByRole("button", { name: "Show activity" }));
    expect(onShowActivity).toHaveBeenCalledWith({ counterparty: "Rina", merchant: undefined, offset: undefined, query: undefined, selected: undefined, state: undefined, unresolvedGroup: undefined });
  });

  it("keeps unresolved descriptors private and applies only the review-state patch", () => {
    const onShowActivity = vi.fn();
    const unresolved = {
      ...group({
        key: "unresolved:transaction-3",
        label: "Unresolved statement label",
        kind: "unresolved",
        status: "unresolved",
        transactionCount: 3,
        lastActivityDate: "2026-04-20",
        flows: [{ currency: "AED", sent_minor: 8700, received_minor: 0, net_minor: -8700, transaction_count: 3 }],
      }),
      descriptor: "PRIVATE STATEMENT DESCRIPTOR",
    };
    render(<MerchantView scope="All local activity" flows={scopeFlows} peoplePlaces={[unresolved]} onShowActivity={onShowActivity} />);

    expect(screen.getByRole("heading", { name: "Needs review" })).toBeTruthy();
    const card = screen.getByRole("article", { name: "Unresolved statement label" });
    expect(card.textContent).toContain("Needs review");
    expect(card.textContent).not.toContain("PRIVATE STATEMENT DESCRIPTOR");
    fireEvent.click(within(card).getByRole("button", { name: "Review in activity" }));
    expect(onShowActivity).toHaveBeenCalledWith({ counterparty: undefined, merchant: undefined, offset: undefined, query: undefined, selected: undefined, state: undefined, unresolvedGroup: "transaction-3" });
  });

  it("uses the structured merchant filter for messy place aliases", () => {
    const onShowActivity = vi.fn();
    render(<MerchantView scope="All local activity" flows={scopeFlows} peoplePlaces={[group({})]} onShowActivity={onShowActivity} />);

    fireEvent.click(screen.getByRole("button", { name: "Show activity" }));
    expect(onShowActivity).toHaveBeenCalledWith({ counterparty: undefined, merchant: "Cafe North", offset: undefined, query: undefined, selected: undefined, state: undefined, unresolvedGroup: undefined });
  });

  it("uses scoped empty and direct local error messages", () => {
    const { rerender } = render(<MerchantView scope="All local activity" flows={[]} peoplePlaces={[]} onShowActivity={vi.fn()} />);
    expect(screen.getByText("There are no people or places in this period.")).toBeTruthy();
    expect(screen.queryByText("No trusted activity matches this scope yet.")).toBeNull();

    rerender(<MerchantView scope="All local activity" flows={[]} peoplePlaces={[]} onShowActivity={vi.fn()} loadError="People and places could not be loaded from the local record." />);
    expect(screen.getByRole("status").textContent).toBe("People and places could not be loaded from the local record.");
    expect(screen.queryByText("There are no people or places in this period.")).toBeNull();
  });
});
