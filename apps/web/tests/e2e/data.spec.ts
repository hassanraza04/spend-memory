import { expect, fixturePath, importStatement, test } from "./fixtures";

test("exports the active trusted scope and requires exact local deletion confirmation", async ({ page, freshRecord, rebuildAnalytics }) => {
  await freshRecord(page);
  await importStatement(page, rebuildAnalytics, fixturePath("source", "aed_january_2026.csv"), "?after=2026-01-01&before=2026-02-01");
  await page.getByRole("link", { name: "Data" }).click();
  const download = page.waitForEvent("download");
  await page.getByRole("link", { name: "Export current CSV" }).click();
  expect((await download).suggestedFilename()).toMatch(/transactions\.csv/);

  await page.getByRole("button", { name: "Delete local data" }).click();
  await expect(page.getByRole("button", { name: "Permanently delete local data" })).toBeDisabled();
  await page.getByLabel("Type DELETE LOCAL DATA").fill("DELETE LOCAL DATA");
  await page.getByRole("button", { name: "Permanently delete local data" }).click();
  await expect(page.getByRole("heading", { name: "What happened this month?" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Explore the synthetic demo" })).toBeVisible();
});
