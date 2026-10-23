import { defineConfig, devices } from "@playwright/test";
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH;
const port = process.env.PLAYWRIGHT_PORT ?? "3100";
// Run the same outage assertions against a separately started connected provider.
const connected = process.env.PLAYWRIGHT_CONNECTED === "true";
// PLAYWRIGHT_PROD exercises the production bundle instead of the dev server;
// NEXT_PUBLIC_DEMO_MODE is build-time inlined, so the demo build needs its own
// dist directory and must not race the dev server on the same port.
const prod = process.env.PLAYWRIGHT_PROD === "true";
export default defineConfig({
  testDir: "./e2e", testMatch: connected ? "connected.spec.ts" : /(?:smoke|portfolio-demo|a11y)\.spec\.ts/,
  fullyParallel: false, forbidOnly: !!process.env.CI, retries: process.env.CI ? 2 : 0, workers: 1,
  reporter: [["list"], ["html", { open: "never" }]],
  use: { baseURL: `http://localhost:${port}`, trace: "on-first-retry", launchOptions: executablePath ? { executablePath } : undefined },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: prod ? "npm run build && npm run start" : `npm run dev -- -p ${port}`,
    env: {
      ...process.env,
      NEXT_DIST_DIR: prod ? ".next-demo" : ".next",
      NEXT_PUBLIC_DEMO_MODE: connected ? "false" : "true",
      NEXT_PUBLIC_API_URL: "http://127.0.0.1:9",
      PORT: port,
    },
    url: `http://localhost:${port}`,
    reuseExistingServer: process.env.PLAYWRIGHT_REUSE_SERVER === "true",
    timeout: prod ? 300_000 : 120_000,
  },
});
