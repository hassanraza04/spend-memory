import { expect, fixturePath, importStatement, resetDemo, test } from "./fixtures";

test("opens grouped place activity inside the synthetic demo scope", async ({ page, freshRecord }) => {
  test.slow();
  await freshRecord();
  await resetDemo(page, "?after=2026-01-01&before=2026-04-01");
  await expect(page).toHaveURL(/after=2026-01-01.*before=2026-04-01/);
  await page.getByRole("link", { name: "People & places" }).click();
  await expect(page).toHaveURL(/view=people-places.*after=2026-01-01.*before=2026-04-01/);
  const card = page.getByRole("article", { name: "MetroMart" });
  await expect(card).toContainText("3 transactions");
  await expect(card).toContainText("AED\u00a0276.00");
  await card.getByRole("button", { name: "Show activity" }).click();
  await expect(page).toHaveURL(/view=all-activity.*after=2026-01-01.*before=2026-04-01.*merchant=MetroMart/);
  await expect(page.getByRole("heading", { name: "All activity" })).toBeVisible();
});

test("shows a recurring pattern in the default April synthetic demo", async ({ page, freshRecord }) => {
  await freshRecord();
  await resetDemo(page, "");
  await expect(page).toHaveURL(/after=2026-04-01.*before=2026-05-01/);
  await page.getByRole("link", { name: "Patterns" }).click();
  await expect(page).toHaveURL(/view=patterns.*after=2026-04-01.*before=2026-05-01/);
  await expect(page.getByRole("heading", { name: "The payments that keep coming back" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Streambox" })).toBeVisible();
});

test("shows possible duplicate evidence from the synthetic PKR statement", async ({ page, freshRecord }) => {
  await freshRecord();
  await importStatement(page, fixturePath("source", "pkr_statement_compact.pdf"));
  await page.goto("/?view=patterns&after=2024-09-01&before=2024-10-01");
  await expect(page).toHaveURL(/view=patterns.*after=2024-09-01.*before=2024-10-01/);
  await expect(page.getByRole("heading", { name: "A few things worth checking" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Possible duplicate" })).toBeVisible();
});
