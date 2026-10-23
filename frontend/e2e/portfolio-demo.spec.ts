import { expect, test } from "@playwright/test";
const DRAFT = "/runs/c9d0e1f2";
test.beforeEach(async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
  (page as unknown as { appErrors: string[] }).appErrors = errors;
});
test.afterEach(async ({ page }) => {
  expect((page as unknown as { appErrors: string[] }).appErrors).toEqual([]);
});
test("complete guided journey, keyboard review, one execution, and reset", async ({ page }) => {
  const backend: string[] = [];
  page.on("request", request => { if (request.url().includes(":9/") || request.url().includes(":8000/")) backend.push(request.url()); });
  await page.goto("/");
  await page.getByRole("link", { name: "Start guided demo" }).click();
  await expect(page.getByRole("complementary", { name: "Guided demo" })).toContainText("1 / 5");
  await expect(page.getByRole("heading", { name: "Validated. Permitted. Completed." })).toBeVisible();
  await page.getByText("Inspect proposed tool", { exact: true }).click();
  await expect(page.getByText('"expression": "1450 * 32"')).toBeVisible();
  await page.getByRole("link", { name: "Next step" }).click();
  const reject = page.getByRole("button", { name: "Reject draft", exact: true });
  await reject.focus(); await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "Rejected. Not executed." })).toBeVisible();
  await expect(page.locator(".outcome-panel")).toBeFocused();
  await page.getByRole("button", { name: "Reset this scenario" }).click();
  await page.getByRole("button", { name: "Approve draft", exact: true }).dblclick();
  await expect(page.getByRole("heading", { name: "Approved. Simulated exactly once." })).toBeVisible();
  await expect(page.getByText("Simulated executions in this demo: 1", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve draft", exact: true })).toHaveCount(0);
  await page.getByRole("link", { name: "Next step" }).click();
  await expect(page.getByRole("heading", { name: "Denied. Nothing executed." })).toBeVisible();
  await page.getByRole("link", { name: "Next step" }).click();
  await expect(page.getByTestId("skills-view")).toContainText("Why loaded");
  await expect(page.getByTestId("skills-view")).toContainText("does not grant tool permission");
  await page.getByRole("link", { name: "Next step" }).click();
  await expect(page.getByRole("heading", { name: "Make the boundary testable." })).toBeVisible();
  await page.getByRole("link", { name: "Finish tour" }).click();
  await expect(page.getByRole("complementary", { name: "Guided demo" })).toHaveCount(0);
  await page.getByRole("button", { name: "Reset demo", exact: true }).click();
  await page.getByTestId("run-list").getByRole("link").filter({ hasText: "Draft an email" }).click();
  await expect(page.getByRole("button", { name: "Approve draft", exact: true })).toBeVisible();
  expect(backend).toEqual([]);
});
test("free exploration shares state across approvals, runs, and chat; reload resets", async ({ page }) => {
  await page.goto("/"); await page.getByRole("link", { name: "Explore freely" }).click();
  await expect(page).toHaveURL(/\/runs$/);
  await expect(page.getByRole("complementary", { name: "Guided demo" })).toHaveCount(0);
  await page.getByRole("link", { name: "Approvals", exact: true }).click();
  await page.getByTestId("approval-apr-77ce42aa10bd").getByRole("button", { name: "Approve", exact: true }).click();
  await expect(page.getByTestId("approval-apr-77ce42aa10bd")).toContainText("Simulated once");
  await page.getByRole("link", { name: "run c9d0e1f2", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Approved. Simulated exactly once." })).toBeVisible();
  await page.getByRole("link", { name: "Chat", exact: true }).click();
  await page.getByRole("button", { name: "Draft an email to ops@example.test", exact: true }).click();
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByTestId("chat-thread")).toContainText("Simulated executions: 1");
  await page.reload();
  await page.getByRole("link", { name: "Approvals", exact: true }).click();
  await expect(page.getByTestId("approval-apr-77ce42aa10bd").getByRole("button", { name: "Approve", exact: true })).toBeVisible();
});
test("expiry needs a new approval and unsupported prompts stay honest", async ({ page }) => {
  await page.goto(DRAFT);
  await page.getByRole("button", { name: "Simulate expiry" }).click();
  await expect(page.getByRole("heading", { name: "Expired. Not executed." })).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve draft", exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "Request new review" }).click();
  await page.getByText("Inspect approval", { exact: true }).click();
  await expect(page.getByText(/"id": "apr-new-review-1"/)).toBeVisible();
  await page.getByRole("link", { name: "Chat", exact: true }).click();
  await page.getByLabel("Message the agent").fill("What is 7 * 8?");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByTestId("chat-thread")).toContainText("Preview limitation");
  await expect(page.getByTestId("chat-thread")).not.toContainText("46400");
});
for (const viewport of [{ width: 390, height: 844 }, { width: 768, height: 1024 }, { width: 1440, height: 900 }]) {
  test(`responsive readable keyboard story ${viewport.width}x${viewport.height}`, async ({ page }) => {
    await page.setViewportSize(viewport); await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/");
    await page.keyboard.press("Tab"); await expect(page.getByRole("link", { name: "Skip to content" })).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("heading", { name: /An agent you can/ })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(await page.locator("nav .overflow-x-auto").evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true);
    await page.getByRole("link", { name: "Start guided demo" }).click();
    await page.getByRole("button", { name: "Pause tour", exact: true }).click();
    await expect(page.getByRole("link", { name: "Next step" })).toHaveCount(0);
    await page.getByRole("button", { name: "Resume tour", exact: true }).click();
    await page.getByRole("link", { name: "Next step" }).click();
    await expect(page.getByRole("list", { name: "Request to execution timeline" }).getByRole("listitem")).toHaveCount(5);
    await page.getByRole("button", { name: "Approve draft", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Approved. Simulated exactly once." })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}

test("reset restores a paused tour to its initial unpaused state", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Start guided demo" }).click();
  await page.getByRole("button", { name: "Pause tour", exact: true }).click();
  await page.getByRole("button", { name: "Reset demo", exact: true }).click();
  await page.getByRole("link", { name: /A ARIA/ }).click();
  await page.getByRole("link", { name: "Start guided demo" }).click();
  await expect(page.getByRole("link", { name: "Next step", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Pause tour", exact: true })).toBeVisible();
});
