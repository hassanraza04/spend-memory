import { expect, resetDemo, test } from "./fixtures";

test("explores the synthetic demo with source evidence and a grouped AED flow", async ({ page, freshRecord }) => {
  await freshRecord();
  await resetDemo(page, "");
  await expect(page).toHaveURL(/after=2026-04-01&before=2026-05-01/);
  await expect(page.getByRole("row").nth(1)).toBeVisible();

  await page.getByLabel("Search activity").fill("METROMART POS");
  await page.getByRole("button", { name: "Apply filters" }).click();
  const row = page.getByRole("row", { name: /MetroMart/ }).first();
  await expect(row).toBeVisible();
  await expect(row).not.toContainText("METROMART POS");
  await row.click();
  const sourcePanel = page.getByRole("complementary", { name: "Source evidence" });
  const statementText = sourcePanel.getByText("Statement text", { exact: true }).locator("..");
  await expect(statementText).toHaveText(/Statement text\s*METROMART POS/);
  await page.getByRole("button", { name: "Use this statement label for MetroMart" }).click();
  await expect(page.getByText("Merchant correction saved.")).toBeVisible();
  await page.getByRole("button", { name: "Close source evidence" }).click();

  await page.getByLabel("Group MetroMart").first().check();
  await page.getByLabel("Counterparty name").fill("Weekend groceries");
  await page.getByRole("button", { name: "Create and group" }).click();
  const flow = page.getByRole("region", { name: "Result summary" }).getByLabel("AED flow");
  await expect(flow).toContainText(/Sent[\s\S]*125\.00/);
  await expect(flow).toContainText(/Received[\s\S]*0\.00/);
  await expect(flow).toContainText(/Net flow[\s\S]*-AED[\s\S]*125\.00/);
});

test("shows the complete API-derived result summary after searching demo activity", async ({ page, freshRecord }) => {
  await freshRecord();
  await resetDemo(page);

  await page.getByLabel("Search activity").fill("Fuel");
  await page.getByRole("button", { name: "Apply filters" }).click();
  await expect(page.getByRole("row", { name: /Orbit Fuel/ })).toBeVisible();

  const summary = page.getByRole("region", { name: "Result summary" });
  await expect(summary).toBeVisible();
  await expect(summary).toContainText(/all matching entries/i);
  await expect(summary).toContainText("AED");
});

test("keeps the personal record readable at each supported viewport", async ({ page, freshRecord }, testInfo) => {
  expect(testInfo.snapshotPath("wide-desktop.png", { kind: "screenshot" })).toMatch(new RegExp(`wide-desktop-${process.platform}\\.png$`));
  await freshRecord();
  await resetDemo(page);
  await expect(page.getByText("Synthetic demo")).toBeVisible();
  await page.locator(".demo-label").evaluate((element) => element.remove());

  for (const [name, width, height] of [["wide-desktop", 1600, 1000], ["laptop", 1280, 800], ["tablet", 768, 1024], ["mobile", 390, 844]] as const) {
    await page.setViewportSize({ width, height });
    await page.evaluate(() => window.scrollTo(0, 0));
    await expect(page).toHaveScreenshot(`${name}.png`);
  }
});
