import { expect, reloadTrustedRecord, test, waitForWorkspaceRefresh } from "./fixtures";

test("explores the synthetic demo with source evidence and a grouped AED flow", async ({ page, freshRecord, rebuildAnalytics }) => {
  await freshRecord();
  const refreshed = waitForWorkspaceRefresh(page);
  await page.getByRole("button", { name: "Explore the synthetic demo" }).click();
  await expect(page.getByText("Synthetic demo data is ready.")).toBeVisible();
  await refreshed;
  await reloadTrustedRecord(page, rebuildAnalytics, "?after=2026-01-01&before=2026-02-01");

  await page.getByLabel("Search activity").fill("MetroMart");
  await page.getByRole("button", { name: "Apply filters" }).click();
  const row = page.getByRole("row", { name: /MetroMart POS/ });
  await expect(row).toBeVisible();
  await row.click();
  await expect(page.getByRole("complementary", { name: "Source evidence" })).toContainText("MetroMart POS");

  await page.getByLabel("Group MetroMart POS").check();
  await page.getByLabel("Counterparty name").fill("Weekend groceries");
  await page.getByRole("button", { name: "Create and group" }).click();
  const flow = page.getByLabel("AED flow");
  await expect(flow).toContainText(/Sent[\s\S]*56\.15/);
  await expect(flow).toContainText(/Received[\s\S]*0\.00/);
  await expect(flow).toContainText(/Net flow[\s\S]*-AED[\s\S]*56\.15/);
});

test("keeps the personal record readable at each supported viewport", async ({ page, freshRecord, rebuildAnalytics }) => {
  await freshRecord();
  const refreshed = waitForWorkspaceRefresh(page);
  await page.getByRole("button", { name: "Explore the synthetic demo" }).click();
  await refreshed;
  await reloadTrustedRecord(page, rebuildAnalytics, "?after=2026-01-01&before=2026-02-01");

  for (const [name, width, height] of [["wide-desktop", 1600, 1000], ["laptop", 1280, 800], ["tablet", 768, 1024], ["mobile", 390, 844]] as const) {
    await page.setViewportSize({ width, height });
    await page.evaluate(() => window.scrollTo(0, 0));
    await expect(page).toHaveScreenshot(`${name}.png`);
  }
});
