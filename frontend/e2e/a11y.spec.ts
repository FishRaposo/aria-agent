import { expect, test } from "@playwright/test";
import { AxeBuilder } from "@axe-core/playwright";

// WCAG 2.1 A/AA scan over the demo-mode routes. Critical and serious
// violations fail; minor/moderate findings stay visible in the report without
// blocking, matching how the rest of the suite treats preview evidence.
const routes = [
  { path: "/", name: "home" },
  { path: "/setup", name: "setup" },
  { path: "/chat", name: "chat" },
  { path: "/approvals", name: "approvals" },
  { path: "/runs", name: "runs" },
  { path: "/skills", name: "skills" },
  { path: "/tools", name: "tools" },
  { path: "/memory", name: "memory" },
];

test.describe("accessibility", () => {
  for (const route of routes) {
    test(`${route.name} has no serious accessibility violations`, async ({
      page,
    }) => {
      await page.goto(route.path);
      await expect(page.locator("main").first()).toBeVisible();
      const results = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
        .analyze();
      const blocking = results.violations.filter(
        (violation) =>
          violation.impact === "critical" || violation.impact === "serious"
      );
      expect(
        blocking,
        JSON.stringify(
          blocking.map((violation) => ({
            id: violation.id,
            impact: violation.impact,
            help: violation.help,
            targets: violation.nodes.flatMap((node) => node.target),
          })),
          null,
          1
        )
      ).toEqual([]);
    });
  }
});
