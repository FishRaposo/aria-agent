import nextVitals from "eslint-config-next/core-web-vitals";

const eslintConfig = [
  ...nextVitals,
  {
    rules: {
      // The console's data-loading effects set loading/error state at the
      // start of an async fetch — the standard pre-Suspense pattern. The
      // compiler-era set-state-in-effect rule would force artificial microtask
      // deferrals without changing behavior, so it is disabled project-wide.
      "react-hooks/set-state-in-effect": "off",
    },
  },
  {
    ignores: [
      ".next*/**",
      "node_modules/**",
      "playwright-report/**",
      "test-results/**",
      "next-env.d.ts",
    ],
  },
];

export default eslintConfig;
