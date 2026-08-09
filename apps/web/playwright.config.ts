import { defineConfig } from "@playwright/test";
import { resolve } from "node:path";

const root = resolve(__dirname, "../..");
const dataRoot = resolve(root, ".playwright/worker-0");

export default defineConfig({
  testDir: "tests/e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 60_000,
  expect: {
    timeout: 10_000,
    toHaveScreenshot: { pathTemplate: "{testDir}/{testFilePath}-snapshots/{arg}-{platform}{ext}" },
  },
  use: {
    baseURL: "http://127.0.0.1:3000",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: `mkdir -p ${dataRoot} && UV_CACHE_DIR=.uv-cache SPEND_MEMORY_APP_DATA_ROOT=${dataRoot} SPEND_MEMORY_DATA_DIRECTORY=${dataRoot}/data DUCKDB_PATH=${dataRoot}/spend-memory.duckdb uv run uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 8000`,
      cwd: root,
      url: "http://127.0.0.1:8000/api/v1/health",
      reuseExistingServer: false,
      timeout: 60_000,
      stdout: "ignore",
      stderr: "pipe",
    },
    {
      command: "pnpm --dir apps/web build && pnpm --dir apps/web start",
      cwd: root,
      url: "http://127.0.0.1:3000",
      reuseExistingServer: false,
      timeout: 60_000,
      stdout: "ignore",
      stderr: "ignore",
    },
  ],
});
