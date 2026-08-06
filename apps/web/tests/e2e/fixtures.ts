import { expect, test as base, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { resolve } from "node:path";

const root = resolve(__dirname, "../../../..");
const dataRoot = resolve(root, ".playwright/worker-0");
const databasePath = resolve(dataRoot, "spend-memory.duckdb");

export const fixturePath = (...parts: string[]) => resolve(root, "sample_data", ...parts);

export const test = base.extend<{ freshRecord: () => Promise<void> }>({
  freshRecord: async ({ page }, run) => {
    await run(async () => {
      const cleared = await page.request.delete("http://127.0.0.1:8000/api/v1/local-data", {
        data: { confirmation: "DELETE LOCAL DATA" },
      });
      expect(cleared.ok()).toBe(true);
      await page.addInitScript(() => window.localStorage.clear());
      await page.goto("/");
      const firstRun = page.getByRole("heading", { name: "What happened this month?" });
      await expect(firstRun).toBeVisible();
      await expect(page.getByRole("button", { name: "Explore the synthetic demo" })).toBeEnabled();
    });
  },
});

export { expect };

export async function reloadTrustedRecord(page: Page, search = "") {
  await page.goto(`/${search}`);
  await expect(page.getByText("Here is the exact trusted activity in your current scope.")).toBeVisible();
  await expect(page.getByRole("link", { name: "People & places" })).toBeVisible();
}

export function createMerchant(merchantName: string) {
  execFileSync(
    "uv",
    [
      "run",
      "python",
      "-c",
      "from os import environ; from spend_memory.enrichment.repository import EnrichmentRepository; EnrichmentRepository(environ['SPEND_MEMORY_DUCKDB_PATH']).create_merchant(environ['SPEND_MEMORY_E2E_MERCHANT'])",
    ],
    {
      cwd: root,
      env: {
        ...process.env,
        UV_CACHE_DIR: resolve(root, ".uv-cache"),
        PYTHONPATH: resolve(root, "apps/api"),
        SPEND_MEMORY_DUCKDB_PATH: databasePath,
        SPEND_MEMORY_E2E_MERCHANT: merchantName,
      },
      stdio: "pipe",
    },
  );
}

export async function importStatement(page: Page, path: string, search = new URL(page.url()).search) {
  const imported = page.waitForResponse((response) => (
    response.request().method() === "POST"
    && new URL(response.url()).pathname === "/api/v1/imports"
  ));
  await page.getByLabel("Choose a CSV or PDF").setInputFiles(path);
  await page.getByRole("button", { name: "Import selected statement" }).click();
  expect((await imported).ok()).toBe(true);
  await reloadTrustedRecord(page, search);
}

export async function resetDemo(page: Page, search = "?after=2026-01-01&before=2026-02-01") {
  const reset = page.waitForResponse((response) => (
    response.request().method() === "POST"
    && new URL(response.url()).pathname === "/api/v1/demo/reset"
  ));
  await page.getByRole("button", { name: "Explore the synthetic demo" }).click();
  expect((await reset).ok()).toBe(true);
  await reloadTrustedRecord(page, search);
}
