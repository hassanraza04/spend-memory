import { expect, test as base, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { resolve } from "node:path";

const root = resolve(__dirname, "../../../..");
const dataRoot = resolve(root, ".playwright/worker-0");
const databasePath = resolve(dataRoot, "spend-memory.duckdb");

export const fixturePath = (...parts: string[]) => resolve(root, "sample_data", ...parts);

// eslint-disable-next-line no-unused-vars -- This is the browser page passed to each test fixture.
export const test = base.extend<{ freshRecord: (page: Page) => Promise<void>; rebuildAnalytics: () => void }>({
  freshRecord: async (fixtures, run) => {
    void fixtures;
    await run(async (page) => {
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
  rebuildAnalytics: async (fixtures, run) => {
    void fixtures;
    await run(() => {
      execFileSync("uv", ["run", "dbt", "build", "--project-dir", "analytics", "--profiles-dir", "analytics"], {
        cwd: root,
        env: { ...process.env, UV_CACHE_DIR: resolve(root, ".uv-cache"), SPEND_MEMORY_DUCKDB_PATH: databasePath },
        stdio: "pipe",
      });
    });
  },
});

export { expect };

export async function reloadTrustedRecord(page: Page, rebuildAnalytics: () => void, search = "") {
  rebuildAnalytics();
  await page.goto(`/${search}`);
  await expect(page.getByRole("heading", { name: "What happened this month?" })).toBeVisible();
}

export function refreshEnrichment(rebuildAnalytics: () => void) {
  rebuildAnalytics();
  execFileSync(
    "uv",
    [
      "run",
      "python",
      "-c",
      "from os import environ; from spend_memory.enrichment.repository import EnrichmentRepository; from spend_memory.enrichment.service import EnrichmentService; EnrichmentService(EnrichmentRepository(environ['SPEND_MEMORY_DUCKDB_PATH'])).refresh()",
    ],
    {
      cwd: root,
      env: {
        ...process.env,
        UV_CACHE_DIR: resolve(root, ".uv-cache"),
        PYTHONPATH: resolve(root, "apps/api"),
        SPEND_MEMORY_DUCKDB_PATH: databasePath,
      },
      stdio: "pipe",
    },
  );
  rebuildAnalytics();
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

export async function importStatement(page: Page, rebuildAnalytics: () => void, path: string, search = "") {
  const refreshed = waitForWorkspaceRefresh(page);
  await page.getByLabel("Choose a CSV or PDF").setInputFiles(path);
  await expect(page.getByText("Your record is ready to review.")).toBeVisible();
  await refreshed;
  await reloadTrustedRecord(page, rebuildAnalytics, search);
}

export function waitForWorkspaceRefresh(page: Page) {
  return Promise.all([
    page.waitForResponse((response) => response.url().includes("/api/v1/lens?")),
    page.waitForResponse((response) => response.url().includes("/api/v1/transactions?") && !response.url().includes("limit=1")),
    page.waitForResponse((response) => response.url().includes("/api/v1/transactions?limit=1")),
  ]);
}
