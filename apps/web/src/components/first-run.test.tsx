import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { FirstRun } from "./first-run";

describe("FirstRun", () => {
  const storage = new Map<string, string>();

  beforeEach(() => {
    storage.clear();
    Object.defineProperty(window, "localStorage", {
      configurable: true,
      value: {
        getItem: (key: string) => storage.get(key) ?? null,
        setItem: (key: string, value: string) => storage.set(key, value),
        removeItem: (key: string) => storage.delete(key),
      },
    });
  });

  afterEach(() => vi.unstubAllGlobals());

  it("explains that statements stay on this device", () => {
    render(<FirstRun />);

    expect(screen.getByText("Your statements stay on this device.")).toBeTruthy();
  });

  it("offers an import beside a clearly synthetic demo", () => {
    render(<FirstRun />);

    expect(screen.getByRole("button", { name: "Import a statement" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Explore the synthetic demo" })).toBeTruthy();
  });

  it("waits for the local record check before starting an import or demo", () => {
    render(<FirstRun ready={false} />);

    expect(screen.getByRole("button", { name: "Import a statement" })).toHaveProperty("disabled", true);
    expect(screen.getByRole("button", { name: "Explore the synthetic demo" })).toHaveProperty("disabled", true);
  });

  it("explains when a chosen file is unsupported", () => {
    render(<FirstRun />);

    fireEvent.change(screen.getByLabelText("Choose a CSV or PDF"), {
      target: { files: [new File(["hello"], "notes.txt", { type: "text/plain" })] },
    });

    expect(screen.getByText("Choose a CSV or PDF statement.")).toBeTruthy();
  });

  it("describes a partial import without guessing a completion percentage", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            document_id: "11111111-1111-1111-1111-111111111111",
            run_id: "22222222-2222-2222-2222-222222222222",
            transaction_count: 0,
            was_already_imported: false,
          }),
          { status: 201 },
        ),
      ),
    );
    render(<FirstRun />);

    fireEvent.change(screen.getByLabelText("Choose a CSV or PDF"), {
      target: { files: [new File(["date,amount"], "statement.csv", { type: "text/csv" })] },
    });

    expect(await screen.findByText("The statement was read, but no transactions could be reconciled.")).toBeTruthy();
  });

  it("keeps import failures plain and actionable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", { status: 500 })));
    render(<FirstRun />);

    fireEvent.change(screen.getByLabelText("Choose a CSV or PDF"), {
      target: { files: [new File(["date,amount"], "statement.csv", { type: "text/csv" })] },
    });

    expect(await screen.findByText("We could not import that statement. Try another supported file.")).toBeTruthy();
  });

  it("requires demo data to be cleared before a personal import", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: "reset" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: "deleted" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    render(<FirstRun />);

    fireEvent.click(screen.getByRole("button", { name: "Explore the synthetic demo" }));

    expect(await screen.findByRole("button", { name: "Clear demo data" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Import a statement" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Clear demo data" }));

    expect(await screen.findByRole("button", { name: "Import a statement" })).toBeTruthy();
    expect(storage.get("spend-memory-demo-workspace")).toBeUndefined();
    expect(fetchMock).toHaveBeenLastCalledWith(
      "/api/v1/local-data",
      expect.objectContaining({ method: "DELETE" }),
    );
  });

  it("explains a blocked demo reset without using import failure copy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            error: {
              code: "non_demo_imports_present",
              message: "Demo reset is unavailable while local imports are present.",
            },
          }),
          { status: 409 },
        ),
      ),
    );
    render(<FirstRun />);

    fireEvent.click(screen.getByRole("button", { name: "Explore the synthetic demo" }));

    expect(await screen.findByText("The demo cannot replace your imported records.")).toBeTruthy();
    expect(screen.queryByText("We could not import that statement. Try another supported file.")).toBeNull();
  });

  it("keeps personal import unavailable when clearing demo data fails", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: "reset" }), { status: 200 }))
      .mockResolvedValueOnce(new Response("", { status: 500 }));
    vi.stubGlobal("fetch", fetchMock);
    render(<FirstRun />);

    fireEvent.click(screen.getByRole("button", { name: "Explore the synthetic demo" }));
    expect(await screen.findByRole("button", { name: "Clear demo data" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Clear demo data" }));

    expect(await screen.findByText("We could not clear demo data. Your personal data was not changed.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Clear demo data" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Import a statement" })).toBeNull();
    expect(storage.get("spend-memory-demo-workspace")).toBe("true");
  });

  it("restores the demo safety gate after a reload", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: "reset" }), { status: 200 })));
    const firstRender = render(<FirstRun />);

    fireEvent.click(screen.getByRole("button", { name: "Explore the synthetic demo" }));
    expect(await screen.findByRole("button", { name: "Clear demo data" })).toBeTruthy();
    expect(storage.get("spend-memory-demo-workspace")).toBe("true");
    firstRender.unmount();

    render(<FirstRun />);

    expect(screen.getByRole("button", { name: "Clear demo data" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Import a statement" })).toBeNull();
  });
});
