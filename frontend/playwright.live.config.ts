import { defineConfig, devices } from "@playwright/test";

// Actual API process/database are owned by the test fixture, never a sample server.
const port = process.env.ARIA_LIVE_FRONTEND_PORT ?? "3102";
const apiPort = process.env.ARIA_LIVE_API_PORT ?? "8100";
export default defineConfig({
  testDir: "./e2e", testMatch: "live-app.spec.ts", fullyParallel: false,
  workers: 1, retries: 0, timeout: 60_000,
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-live-report" }]],
  use: { baseURL: `http://localhost:${port}`, trace: "retain-on-failure", screenshot: "only-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: process.env.ARIA_LIVE_API_ONLY === "true" ? undefined : {
    command: `npm run build && npm run start -- -p ${port}`,
    env: { ...process.env, NEXT_DIST_DIR: ".next-live", NEXT_PUBLIC_DEMO_MODE: "false", NEXT_PUBLIC_API_URL: `http://127.0.0.1:${apiPort}` },
    url: `http://localhost:${port}`, reuseExistingServer: false, timeout: 180_000,
  },
});
