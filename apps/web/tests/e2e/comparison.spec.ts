import { expect, fixturePath, importStatement, test } from "./fixtures";

test("explains an exact month-to-month change with contribution evidence", async ({ page, freshRecord }) => {
  await freshRecord();
  await importStatement(page, fixturePath("source", "aed_statement_tabular.pdf"));
  await page.goto("/?view=compare&after=2025-02-01&before=2025-03-01&account=AED-SYNTH-001&currency=AED");
  await expect(page.getByRole("heading", { name: "What changed?" })).toBeVisible();
  await expect(page.getByLabel("Exact comparison totals")).toContainText(/Earlier net[\s\S]*-AED[\s\S]*1,497\.70/);
  await expect(page.getByLabel("Exact comparison totals")).toContainText(/Later net[\s\S]*-AED[\s\S]*1,497\.53/);
  await expect(page.getByLabel("Exact comparison totals")).toContainText(/Exact change[\s\S]*AED[\s\S]*0\.17/);
  await expect(page.getByRole("table", { name: "Waterfall text alternative" })).toBeVisible();
  const evidence = page.getByRole("table", { name: "Exact contribution evidence" });
  await expect(evidence.getByRole("row", { name: /orbit fuel[\s\S]*-AED[\s\S]*299\.13[\s\S]*5/ })).toBeVisible();
  await expect(evidence.getByRole("row", { name: /metro mart[\s\S]*AED[\s\S]*279\.31[\s\S]*3/ })).toBeVisible();
  await expect(evidence.getByRole("row", { name: /qkcrt online[\s\S]*-AED[\s\S]*185\.21[\s\S]*4/ })).toBeVisible();
});
