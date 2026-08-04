import { expect, fixturePath, importStatement, test } from "./fixtures";

test("explains an exact month-to-month change with contribution evidence", async ({ page, freshRecord, rebuildAnalytics }) => {
  await freshRecord(page);
  await importStatement(page, rebuildAnalytics, fixturePath("source", "aed_statement_tabular.pdf"));
  await page.goto("/?view=compare&after=2025-02-01&before=2025-03-01&account=AED-SYNTH-001&currency=AED");
  await expect(page.getByRole("heading", { name: "What changed?" })).toBeVisible();
  await expect(page.getByRole("table", { name: "Waterfall text alternative" })).toBeVisible();
  await expect(page.getByRole("table", { name: "Exact contribution evidence" })).toBeVisible();
});
