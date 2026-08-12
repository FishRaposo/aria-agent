import { expect, test } from "@playwright/test";

// Smoke E2E over the demo-mode UI. The dev server runs with no backend, so
// every view falls back to bundled mock data and shows a "Demo mode" badge.

test("home page loads with hero and nav", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveTitle(/ARIA/i);
  await expect(
    page.getByRole("heading", { name: /ARIA Agent Control Console/i })
  ).toBeVisible();
});

test("runs view shows demo data and charts", async ({ page }) => {
  await page.goto("/runs");
  await expect(page.getByTestId("demo-badge").first()).toBeVisible();
  await expect(page.getByTestId("run-list")).toBeVisible();
  await expect(page.getByTestId("cost-chart")).toBeVisible();
});

test("run detail opens a trace timeline", async ({ page }) => {
  await page.goto("/runs");
  await page.getByTestId("run-list").locator("a").first().click();
  await expect(page.getByTestId("trace-timeline")).toBeVisible();
});

test("tools registry lists builtin tools", async ({ page }) => {
  await page.goto("/tools");
  await expect(page.getByTestId("tool-list")).toBeVisible();
  await expect(page.getByText("calculator")).toBeVisible();
});

test("approval queue renders approve/reject controls", async ({ page }) => {
  await page.goto("/approvals");
  await expect(page.getByTestId("approval-list")).toBeVisible();
  await expect(page.getByText("Approve").first()).toBeVisible();
});

test("chat runs a turn locally in demo mode", async ({ page }) => {
  await page.goto("/chat");
  await page.getByLabel("Message the agent").fill("What is 1450 * 32?");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText("calculator")).toBeVisible();
});
