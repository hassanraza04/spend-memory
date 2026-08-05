import type { Page as ApiPage } from "../../src/lib/api";

import { createMerchant, expect, fixturePath, importStatement, refreshEnrichment, reloadTrustedRecord, test } from "./fixtures";

type MerchantEvidence = {
  transaction_id: string;
  merchant_name: string | null;
  status: string;
  method: string;
  evidence: Record<string, string | number>;
};

async function merchants(page: import("@playwright/test").Page): Promise<MerchantEvidence[]> {
  const response = await page.request.get("http://127.0.0.1:8000/api/v1/merchants?limit=100");
  expect(response.ok()).toBe(true);
  return ((await response.json()) as ApiPage<MerchantEvidence>).items;
}

test("inspects recurring evidence and saves a merchant correction locally", async ({ page, freshRecord, rebuildAnalytics }) => {
  const scope = "?after=2024-01-01&before=2024-04-01";
  await freshRecord();
  await importStatement(page, rebuildAnalytics, fixturePath("source", "aed_statement_tabular.pdf"), scope);
  await expect(page).toHaveURL(/after=2024-01-01.*before=2024-04-01/);
  createMerchant("METROMART POS");
  refreshEnrichment(rebuildAnalytics);
  await reloadTrustedRecord(page, rebuildAnalytics, scope);
  await page.getByRole("link", { name: "Patterns" }).click();
  await expect(page).toHaveURL(/view=patterns.*after=2024-01-01.*before=2024-04-01/);
  await expect(page.getByRole("heading", { name: "The payments that keep coming back" })).toBeVisible();
  await expect(page.getByRole("heading", { name: /streambox monthly/i })).toBeVisible();

  await page.getByRole("link", { name: "People & places" }).click();
  await expect(page).toHaveURL(/view=people-places.*after=2024-01-01.*before=2024-04-01/);
  const seeded = (await merchants(page)).find((merchant) => (
    merchant.merchant_name === "METROMART POS"
    && merchant.status === "suggested"
    && merchant.evidence.normalized_descriptor === "metromart pos"
  ));
  expect(seeded).toBeDefined();
  if (!seeded) throw new Error("The seeded merchant suggestion was not available.");
  const card = page.getByTestId(`merchant-card-${seeded.transaction_id}`);
  const correction = card.getByLabel("Exact statement label for METROMART POS");
  await correction.fill("METRO MART");
  await card.getByRole("button", { name: "Save correction for METROMART POS" }).click();
  await expect(page.getByText("Saved.")).toBeVisible();

  refreshEnrichment(rebuildAnalytics);
  await reloadTrustedRecord(page, rebuildAnalytics, scope);
  await page.getByRole("link", { name: "People & places" }).click();
  await expect(page).toHaveURL(/view=people-places.*after=2024-01-01.*before=2024-04-01/);
  const resolved = (await merchants(page)).find((merchant) => (
    merchant.status === "confirmed"
    && merchant.method === "confirmed_alias"
    && merchant.evidence.normalized_descriptor === "metro mart"
  ));
  expect(resolved).toBeDefined();
  if (!resolved) throw new Error("The corrected merchant alias was not available.");
  const exactAlias = page.getByTestId(`merchant-card-${resolved.transaction_id}`);
  await expect(exactAlias).toContainText("Confirmed");
  await expect(exactAlias).toHaveAttribute("data-resolution-method", "confirmed_alias");
  await expect(exactAlias).toHaveAttribute("data-normalized-descriptor", "metro mart");
});

test("shows possible duplicate evidence from the synthetic PKR statement", async ({ page, freshRecord, rebuildAnalytics }) => {
  await freshRecord();
  await importStatement(page, rebuildAnalytics, fixturePath("source", "pkr_statement_compact.pdf"));
  refreshEnrichment(rebuildAnalytics);
  await page.reload();
  await page.getByRole("link", { name: "Patterns" }).click();
  await expect(page.getByRole("heading", { name: "A few things worth checking" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Possible duplicate" })).toBeVisible();
});
