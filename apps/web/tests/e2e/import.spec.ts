import { expect, fixturePath, importStatement, test } from "./fixtures";
import { readFileSync } from "node:fs";

test("imports and reconciles a synthetic CSV without duplicating a retry", async ({ page, freshRecord, rebuildAnalytics }) => {
  await freshRecord();
  const csv = fixturePath("source", "aed_january_2026.csv");
  await importStatement(page, rebuildAnalytics, csv, "?after=2026-01-01&before=2026-02-01");
  await expect(page.getByText(/17 trusted entries/)).toBeVisible();

  const retry = await page.request.post("/api/v1/imports", {
    multipart: { file: { name: "aed_january_2026.csv", mimeType: "text/csv", buffer: readFileSync(csv) } },
  });
  expect(retry.ok()).toBe(true);
  expect((await retry.json()).was_already_imported).toBe(true);
});

test("imports the scanned synthetic PDF through the OCR-capable local path", async ({ page, freshRecord }) => {
  await freshRecord();
  await page.getByLabel("Choose a CSV or PDF").setInputFiles(fixturePath("source", "aed_statement_image_only.pdf"));
  await page.getByRole("button", { name: "Import selected statement" }).click();
  await expect(page.getByText("Your record is ready to review.")).toBeVisible();
});
