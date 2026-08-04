import { createMerchant, expect, fixturePath, importStatement, refreshEnrichment, test } from "./fixtures";

test("inspects recurring evidence and saves a merchant correction locally", async ({ page, freshRecord, rebuildAnalytics }) => {
  await freshRecord(page);
  await importStatement(page, rebuildAnalytics, fixturePath("source", "aed_statement_tabular.pdf"));
  createMerchant("METROMART POS");
  refreshEnrichment(rebuildAnalytics);
  await page.reload();
  await page.getByRole("link", { name: "Patterns" }).click();
  await expect(page.getByRole("heading", { name: "The payments that keep coming back" })).toBeVisible();
  await expect(page.getByRole("heading", { name: /streambox monthly/i })).toBeVisible();

  await page.getByRole("link", { name: "People & places" }).click();
  const correction = page.getByLabel(/Exact statement label for/).first();
  await correction.fill("METRO MART");
  await page.getByRole("button", { name: /Save correction for/ }).first().click();
  await expect(page.getByText("Saved.")).toBeVisible();

  refreshEnrichment(rebuildAnalytics);
  await page.reload();
  await expect(page.getByText("Confirmed").first()).toBeVisible();
});

test("shows possible duplicate evidence from the synthetic PKR statement", async ({ page, freshRecord, rebuildAnalytics }) => {
  await freshRecord(page);
  await importStatement(page, rebuildAnalytics, fixturePath("source", "pkr_statement_compact.pdf"));
  refreshEnrichment(rebuildAnalytics);
  await page.reload();
  await page.getByRole("link", { name: "Patterns" }).click();
  await expect(page.getByRole("heading", { name: "A few things worth checking" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Possible duplicate" })).toBeVisible();
});
