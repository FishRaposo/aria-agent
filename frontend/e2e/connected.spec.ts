import { expect, test } from "@playwright/test";
test("connected outage is an error until the user explicitly enters samples", async ({ page }) => {
  await page.goto("/runs");
  await expect(page.getByTestId("provider-label")).toHaveText(/Connected API mode/);
  await expect(page.getByTestId("error-state")).toContainText("Could not connect");
  await expect(page.getByTestId("run-list")).toHaveCount(0);
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(page.getByTestId("error-state")).toBeVisible();
  await page.getByTestId("error-state").getByRole("button", { name: "Enter sample demo", exact: true }).click();
  await expect(page.getByTestId("provider-label")).toContainText("Interactive sample data");
  await expect(page.getByTestId("run-list")).toBeVisible();
  await expect(page.getByTestId("error-state")).toHaveCount(0);
});

test("connected chat offers an actual retry and explicit sample recovery", async ({ page }) => {
  const requests: string[] = [];
  page.on("request", request => { if (request.url().includes("/agent/chat")) requests.push(request.url()); });
  await page.goto("/chat");
  await page.getByLabel("Message the agent").fill("What is 7 * 8?");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByTestId("chat-thread")).toContainText("Could not connect");
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect.poll(() => requests.length).toBe(2);
  await page.getByTestId("chat-thread").getByRole("button", { name: "Enter sample demo", exact: true }).first().click();
  await expect(page.getByTestId("provider-label")).toContainText("Interactive sample data");
  await expect(page.getByRole("button", { name: "What is 1450 * 32?", exact: true })).toBeVisible();
  await expect(page.getByTestId("chat-thread")).not.toContainText("Could not connect");
});
