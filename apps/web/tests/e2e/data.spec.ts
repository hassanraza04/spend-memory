import { readFile } from "node:fs/promises";

import { expect, fixturePath, importStatement, test } from "./fixtures";

test("exports the active trusted scope and requires exact local deletion confirmation", async ({ page, freshRecord, rebuildAnalytics }) => {
  await freshRecord();
  await importStatement(page, rebuildAnalytics, fixturePath("source", "aed_january_2026.csv"), "?after=2026-01-01&before=2026-02-01");
  await page.getByLabel("Search activity").fill("MetroMart POS");
  await page.getByRole("button", { name: "Apply filters" }).click();
  await page.getByLabel("Group MetroMart POS").check();
  await page.getByLabel("Counterparty name").fill("=Weekend groceries");
  await page.getByRole("button", { name: "Create and group" }).click();
  await expect(page.getByText("Grouped under =Weekend groceries.")).toBeVisible();

  await expect(page).toHaveURL(/after=2026-01-01.*before=2026-02-01/);
  await page.getByRole("link", { name: "Data" }).click();
  await expect(page).toHaveURL(/view=data.*after=2026-01-01.*before=2026-02-01/);
  const download = page.waitForEvent("download");
  await page.getByRole("link", { name: "Export current CSV" }).click();
  const exported = await download;
  expect(exported.suggestedFilename()).toMatch(/transactions\.csv/);
  const path = await exported.path();
  expect(path).not.toBeNull();
  const csv = await readFile(path!, "utf8");
  const rows = csv.trimEnd().split(/\r?\n/);
  expect(rows).toHaveLength(18);
  expect(rows[0]).toContain("transaction_id,transaction_date,account,description");
  expect(csv).toContain("MetroMart POS");
  expect(csv).not.toContain("BREW-LAB");
  expect(csv).toContain("'=Weekend groceries");

  await page.getByRole("button", { name: "Delete local data" }).click();
  await expect(page.getByRole("button", { name: "Permanently delete local data" })).toBeDisabled();
  await page.getByLabel("Type DELETE LOCAL DATA").fill("DELETE LOCAL DATA");
  await page.getByRole("button", { name: "Permanently delete local data" }).click();
  await expect(page.getByRole("heading", { name: "What happened this month?" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Explore the synthetic demo" })).toBeVisible();
});
