import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DataView } from "./data-view";

describe("DataView", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("links the active scope to a safe CSV export", () => {
    render(<DataView scope={{ account: "Daily", currency: "AED" }} />);
    expect(screen.getByRole("link", { name: "Export current CSV" }).getAttribute("href")).toContain("account=Daily");
  });

  it("requires the exact typed confirmation and closes with Escape", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: "deleted" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    render(<DataView scope={{}} />);

    fireEvent.click(screen.getByRole("button", { name: "Delete local data" }));
    expect(screen.getByRole("dialog", { name: "Delete local data" })).toBeTruthy();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("dialog", { name: "Delete local data" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Delete local data" }));
    fireEvent.change(screen.getByLabelText("Type DELETE LOCAL DATA"), { target: { value: "DELETE LOCAL DATA" } });
    fireEvent.click(screen.getByRole("button", { name: "Permanently delete local data" }));

    expect(await screen.findByText("Local data deleted.")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/local-data", expect.objectContaining({ method: "DELETE" }));
  });

  it("keeps the local API error in the delete result", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { code: "unsafe_local_data_path", message: "Local data could not be deleted safely." } }), { status: 409 })));
    render(<DataView scope={{}} />);

    fireEvent.click(screen.getByRole("button", { name: "Delete local data" }));
    fireEvent.change(screen.getByLabelText("Type DELETE LOCAL DATA"), { target: { value: "DELETE LOCAL DATA" } });
    fireEvent.click(screen.getByRole("button", { name: "Permanently delete local data" }));

    expect(await screen.findByText("Local data was not deleted. Local data could not be deleted safely.")).toBeTruthy();
  });
});
