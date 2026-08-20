import type { Locator } from "@playwright/test";

import { expect, resetDemo, test } from "./fixtures";

type ControlBox = { name: string; x: number; y: number; width: number; height: number; right: number; bottom: number };

async function controlBox(name: string, locator: Locator): Promise<ControlBox> {
  await expect(locator, `${name} should be visible`).toBeVisible();
  const box = await locator.boundingBox();
  expect(box, `${name} should have layout geometry`).not.toBeNull();
  return { name, ...box!, right: box!.x + box!.width, bottom: box!.y + box!.height };
}

function overlaps(first: ControlBox, second: ControlBox) {
  return first.x < second.right && first.right > second.x && first.y < second.bottom && first.bottom > second.y;
}

test("keeps activity controls collision-free at each supported viewport", async ({ page, freshRecord }, testInfo) => {
  await freshRecord();
  await resetDemo(page);
  const issues: string[] = [];
  const geometry: Record<number, ControlBox[]> = {};

  for (const width of [1600, 1280, 1024, 768, 390]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 });
    await expect(page.getByRole("button", { name: "Apply filters" })).toBeVisible();

    const controls = await Promise.all([
      controlBox("Search activity", page.getByRole("textbox", { name: "Search activity" })),
      controlBox("Account", page.getByRole("textbox", { name: "Account" })),
      controlBox("Currency", page.getByRole("textbox", { name: "Currency", exact: true })),
      controlBox("Direction", page.getByRole("combobox", { name: "Direction" })),
      controlBox("Sort", page.getByRole("combobox", { name: "Sort" })),
      controlBox("Order", page.getByRole("combobox", { name: "Order" })),
      controlBox("More filters", page.getByText("More filters", { exact: true })),
      controlBox("Apply filters", page.getByRole("button", { name: "Apply filters" })),
    ]);
    const form = await page.locator("form.activity-filters").boundingBox();
    expect(form, `${width}px filter form should have layout geometry`).not.toBeNull();
    const collisions = controls.flatMap((control, index) => controls.slice(index + 1).filter((candidate) => overlaps(control, candidate)).map((candidate) => `${control.name} overlaps ${candidate.name}`));
    const viewport = await page.evaluate(() => ({ scrollWidth: document.documentElement.scrollWidth, innerWidth: window.innerWidth }));

    geometry[width] = controls;
    issues.push(...collisions.map((collision) => `${width}px: ${collision}`));
    if (Math.abs(controls[0].x - form!.x) > 1 || Math.abs(controls[0].right - (form!.x + form!.width)) > 1) issues.push(`${width}px: search does not fill its dedicated row`);
    if (Math.abs(controls.at(-1)!.right - (form!.x + form!.width)) > 1) issues.push(`${width}px: Apply filters is not at the end of its action group`);
    if (viewport.scrollWidth > viewport.innerWidth) issues.push(`${width}px: document is ${viewport.scrollWidth - viewport.innerWidth}px wider than the viewport`);

    if (width === 390) {
      for (let index = 1; index < controls.length; index += 1) {
        if (controls[index].y <= controls[index - 1].y) issues.push(`390px: ${controls[index].name} does not stack after ${controls[index - 1].name}`);
      }
    }
    await page.getByText("More filters", { exact: true }).click();
    const optionalControls = await Promise.all(["From date", "To date", "Minimum amount", "Maximum amount", "Merchant", "Category", "Counterparty", "Review state"].map((name) => controlBox(name, page.getByLabel(name, { exact: true }))));
    const expandedApply = await controlBox("Apply filters", page.getByRole("button", { name: "Apply filters" }));
    const expandedControls = [...controls.slice(0, -1), expandedApply, ...optionalControls];
    issues.push(...expandedControls.flatMap((control, index) => expandedControls.slice(index + 1).filter((candidate) => overlaps(control, candidate)).map((candidate) => `${width}px expanded: ${control.name} overlaps ${candidate.name}`)));
    for (const control of optionalControls) {
      if (control.x < form!.x - 1 || control.right > form!.x + form!.width + 1) issues.push(`${width}px expanded: ${control.name} extends outside the filter form`);
    }
    const expandedViewport = await page.evaluate(() => ({ scrollWidth: document.documentElement.scrollWidth, innerWidth: window.innerWidth }));
    if (expandedViewport.scrollWidth > expandedViewport.innerWidth) issues.push(`${width}px expanded: document is ${expandedViewport.scrollWidth - expandedViewport.innerWidth}px wider than the viewport`);
    if (width === 1024 || width === 390) await page.screenshot({ path: testInfo.outputPath(`activity-layout-expanded-${width}.png`), fullPage: true });
    await page.getByText("More filters", { exact: true }).click();
    if (width === 1024 || width === 390) await page.screenshot({ path: testInfo.outputPath(`activity-layout-${width}.png`), fullPage: true });
  }

  await testInfo.attach("activity-control-geometry", { body: JSON.stringify(geometry, null, 2), contentType: "application/json" });
  expect(issues, `geometry: ${JSON.stringify(geometry)}`).toEqual([]);
});
