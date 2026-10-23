import { defineConfig, devices } from "@playwright/test";
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH;
const port = process.env.PLAYWRIGHT_PORT ?? "3100";
// Run the same outage assertions against a separately started connected provider.
const connected = process.env.PLAYWRIGHT_CONNECTED === "true";
export default defineConfig({
  testDir: "./e2e", testMatch: connected ? "connected.spec.ts" : /(?:smoke|portfolio-demo)\.spec\.ts/,
  fullyParallel: false, forbidOnly: !!process.env.CI, retries: process.env.CI ? 2 : 0, workers: 1,
  reporter: [["list"], ["html", { open: "never" }]],
  use: { baseURL: `http://localhost:${port}`, trace: "on-first-retry", launchOptions: executablePath ? { executablePath } : undefined },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: { command: `npm run dev -- -p ${port}`, env: { ...process.env, NEXT_PUBLIC_DEMO_MODE: connected ? "false" : "true", NEXT_PUBLIC_API_URL: "http://127.0.0.1:9" }, url: `http://localhost:${port}`, reuseExistingServer: process.env.PLAYWRIGHT_REUSE_SERVER === "true", timeout: 120_000 },
});
