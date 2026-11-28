import { expect, test, type Page } from "@playwright/test";

async function open(page: Page) {
  await page.goto("/");
  await expect(page.getByTestId("stat-lap")).toBeVisible();
  await expect(page.getByTestId("car-viewer").locator("canvas")).toBeVisible();
}

async function lapTime(page: Page): Promise<number> {
  const txt = await page.getByTestId("stat-lap").innerText();
  return Number(/([\d.]+) s/.exec(txt)![1]);
}

test("loads the car, 20 components and a healthy baseline", async ({ page }) => {
  await open(page);
  await expect(page.locator("[data-testid^=nav-]")).toHaveCount(20);
  await expect(page.getByTestId("stat-health")).toContainText("100.0%");
  await expect(page.getByTestId("car-overview")).toBeVisible();
  await expect(page.getByText("MODEL-ESTIMATED").first()).toBeVisible();
});

test("selecting a component opens its engineering panel", async ({ page }) => {
  await open(page);
  await page.getByTestId("nav-front_wing").click();
  await expect(page.getByTestId("component-name")).toHaveText("Front Wing");
  await expect(page.getByTestId("analysis-table")).toBeVisible();
  await expect(page.getByText("Failure modes")).toBeVisible();
});

test("damage slider changes the simulated performance", async ({ page }) => {
  await open(page);
  const before = await lapTime(page);
  await page.getByTestId("nav-front_wing").click();
  await page.getByRole("button", { name: "Critical" }).click();
  await expect(page.getByTestId("severity-value")).toHaveText("90%");
  await expect.poll(() => lapTime(page)).toBeGreaterThan(before);
  await expect(page.getByTestId("mechanism")).toBeVisible();
  await expect(page.getByTestId("nav-front_wing")).toContainText("Critical");
  // keyboard control of the slider
  await page.getByRole("slider", { name: "Damage severity" }).focus();
  await page.keyboard.press("Home");
  await expect(page.getByTestId("severity-value")).toHaveText("0%");
});

test("scenario selection applies multiple damages and the dashboard updates", async ({ page }) => {
  await open(page);
  const options = await page.getByTestId("scenario-select").locator("option").allInnerTexts();
  expect(options.length).toBeGreaterThan(2);
  await page.getByTestId("scenario-select").selectOption({ index: 1 });
  await expect(page.getByTestId("stat-health")).not.toContainText("100.0%");
  await expect(page.getByTestId("dashboard")).toBeVisible();
  await expect(page.getByTestId("chart-downforce").locator(".main-svg").first()).toBeVisible();
  await expect(page.getByTestId("chart-impact")).toBeVisible();
});

test("save produces downloadable reports", async ({ page }) => {
  await open(page);
  await page.getByTestId("nav-rear_wing").click();
  await page.getByRole("button", { name: "Severe" }).click();
  await page.getByTestId("save-button").click();
  const links = page.getByTestId("report-links");
  await expect(links).toBeVisible();
  const href = await links.getByRole("link", { name: /JSON/ }).getAttribute("href");
  const res = await page.request.get(href!);
  expect(res.ok()).toBeTruthy();
  const body = await res.json();
  expect(JSON.stringify(body)).toContain("rear_wing");
});

test("AI assistant answers offline with verified numbers", async ({ page }) => {
  await open(page);
  await page.getByRole("button", { name: "AI Assistant", exact: true }).click();
  await expect(page.getByTestId("chat-sidebar")).toBeVisible();
  await page.getByTestId("assistant-input").fill("What is the current state of the car?");
  await page.getByRole("button", { name: "Send question" }).click();
  const meta = page.getByTestId("assistant-meta");
  await expect(meta).toBeVisible();
  await expect(meta).toContainText("Rule-based engine");
  await expect(meta).toContainText("All numbers traced to tool results");
});

test("view controls: camera presets, isolate, hide, x-ray", async ({ page }) => {
  await open(page);
  await page.getByRole("button", { name: "Top view" }).click();
  await expect(page.getByRole("button", { name: "Top view" })).toHaveClass(/text-accent/);
  await page.getByTestId("nav-halo").click();
  await page.getByRole("button", { name: "Isolate", exact: true }).click();
  await expect(page.getByText("Isolated: Halo")).toBeVisible();
  await page.getByRole("button", { name: "Show all" }).first().click();
  await expect(page.getByText("Isolated: Halo")).toHaveCount(0);
  await page.getByRole("button", { name: /X-ray/ }).click();
  await expect(page.getByRole("button", { name: /X-ray/ })).toHaveAttribute("aria-pressed", "true");
});

test("assumptions panel re-runs the simulation", async ({ page }) => {
  await open(page);
  const before = await lapTime(page);
  await page.getByRole("tab", { name: /Assumptions/ }).click();
  const input = page.getByRole("spinbutton", { name: /Combined peak power/ });
  await input.fill("600");
  await input.press("Enter");
  await expect.poll(() => lapTime(page)).toBeGreaterThan(before);
});
