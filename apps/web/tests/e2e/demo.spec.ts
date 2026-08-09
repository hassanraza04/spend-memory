import { expect, resetDemo, test } from "./fixtures";

test("explores the synthetic demo with source evidence and a grouped AED flow", async ({ page, freshRecord }) => {
  await freshRecord();
  await resetDemo(page);

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
