import { expect, test } from "@playwright/test";
import type { APIRequestContext, Page } from "@playwright/test";
import { LiveBackend } from "./live-backend";
import fs from "node:fs";
import path from "node:path";
import { createHash } from "node:crypto";

const digest = (text: string) => createHash("sha256").update(text).digest("hex");
function writeProof(snapshot: unknown, completed: unknown, memory: unknown) {
  const directory = path.join(backend.root, "artifacts/portfolio/connected-evidence");
  fs.mkdirSync(directory, { recursive: true });
  const result = { catalog_count: 5, automatic_skill: "calculator", context_consumed: false,
    authorized_effects: 1, duplicate_status: 409, restart_preserved: true, memory_outcomes: 1,
    session_isolated: true, routing: "keyword", persistence: "sqlite" };
  const observations = { snapshot, completed, memory, provenance: "Actual HTTP requests, browser approval, SQLite count and process restart. Synthetic local data; no API response mocks or model calls." };
  // The semantic summary is stable; raw evidence intentionally retains run IDs.
  const canonical = (value: unknown): string => JSON.stringify(value, (_key, item) => item && typeof item === "object" && !Array.isArray(item) ? Object.fromEntries(Object.entries(item).sort(([a], [b]) => a.localeCompare(b))) : item);
  const reproducibility_hash = digest(canonical(result));
  const files: Record<string, string> = {};
  for (const [name, value] of Object.entries({ "report.json": { result, reproducibility_hash }, "observations.json": observations })) {
    const contents = canonical(value) + "\n"; fs.writeFileSync(path.join(directory, name), contents); files[name] = digest(contents);
  }
  fs.writeFileSync(path.join(directory, "manifest.json"), canonical({ schema_version: 1, reproducibility_hash, files }) + "\n");
  fs.writeFileSync(path.join(directory, "checksums.sha256"), Object.entries(files).sort(([a], [b]) => a.localeCompare(b)).map(([name, hash]) => `${hash}  ${name}\n`).join(""));
}

let backend: LiveBackend;
async function capture(page: Page, name: string) {
  const directory = path.join(backend.root, "artifacts/portfolio/connected-screenshots");
  fs.mkdirSync(directory, { recursive: true });
  await page.screenshot({ path: path.join(directory, `${name}.png`), fullPage: true });
}
test.beforeAll(async () => { backend = new LiveBackend(); await backend.start(); });
test.afterAll(async () => { await backend?.stop(); });

async function send(request: APIRequestContext, session: string, message: string) {
  const response = await request.post(`${backend.url}/agent/chat`, { data: { message, session_id: session, mode: "approval_gated" } });
  expect(response.status()).toBe(200); return response.json();
}
async function readRun(request: APIRequestContext, id: string) {
  const response = await request.get(`${backend.url}/agent/runs/${id}`);
  expect(response.status()).toBe(200); return response.json();
}
async function session(page: Page, name: string) {
  await page.getByLabel("Session", { exact: true }).fill(name);
  await page.getByRole("button", { name: "Use session", exact: true }).click();
}
async function chat(page: Page, message: string) {
  await page.getByLabel("Message the agent").fill(message);
  const response = page.waitForResponse(r => r.url() === `${backend.url}/agent/chat` && r.request().method() === "POST");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  const completed = await response; expect(completed.status()).toBe(200); return completed.json();
}
test.beforeEach(async ({ page }, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  page.on("console", message => {
    // Connection refusal is deliberately caused in the real outage test.
    const expectedOutage = testInfo.title.startsWith("actual outage") && message.text().includes("ERR_CONNECTION_REFUSED");
    if (message.type() === "error" && !expectedOutage) errors.push(message.text());
  });
  (page as unknown as { applicationErrors: string[] }).applicationErrors = errors;
});
test.afterEach(async ({ page }) => { expect((page as unknown as { applicationErrors: string[] }).applicationErrors).toEqual([]); });

// A fixture-only frontend could pass every old browser case while /skills is404.
test("actual API exposes metadata without activating a skill", async ({ request }) => {
  const response = await request.get(`${backend.url}/skills?session_id=fresh`);
  expect(response.status()).toBe(200);
  const snapshot = await response.json();
  expect(snapshot.catalog).toHaveLength(5);
  expect(snapshot.activated).toEqual([]);
  expect(snapshot.context_available).toBe(false);
  expect(backend.sql("select count(*) from agent_runs")[0][0]).toBe(0);
});

test("automatic skills, real approval, session memory and history agree", async ({ page, request }) => {
  await page.goto("/chat"); await session(page, "live-workflow");
  const calculation = await chat(page, "calculate 7 * 8");
  await expect(page.getByTestId("chat-thread")).toContainText("56");
  expect(calculation.skill_context.loaded_instruction_bodies[0].name).toBe("calculator");
  await page.getByRole("link", { name: "Skills", exact: true }).click();
  await page.getByLabel("Skill evidence run").selectOption(calculation.run_id);
  await expect(page.getByTestId("skills-view")).toContainText("calculator");
  await expect(page.getByTestId("skills-view")).toContainText(/automatic/i);
  await capture(page, "skills");
  const evidenceResponse = await request.get(`${backend.url}/skills?session_id=live-workflow&run_id=${calculation.run_id}`);
  const evidence = await evidenceResponse.json();
  expect(evidence.activated[0].selection_method).toBe("automatic");
  expect(evidence.activated[0].content_hash).toMatch(/^[a-f0-9]{64}$/);
  expect(evidence.context_report.context_consumed).toBe(false);

  await page.getByRole("link", { name: "Chat", exact: true }).click();
  const before = backend.sql("select count(*) from created_tasks")[0][0] as number;
  const pending = await chat(page, "create a task to verify connected evidence");
  expect(pending.status).toBe("pending_approval");
  await page.goto(`/runs/${pending.run_id}`);
  await page.getByRole("button", { name: "Approve action", exact: true }).click();
  await expect(page.getByTestId("connected-decision-story")).toContainText(/completed/i);
  await capture(page, "completed");
  const completed = await readRun(request, pending.run_id);
  expect(completed.status).toBe("completed");
  expect(completed.approval.execution_status).toBe("completed");
  expect(backend.sql("select count(*) from created_tasks")[0][0]).toBe(before + 1);
  const duplicate = await request.post(`${backend.url}/approvals/${pending.approval.id}/approve`, { data: {} });
  expect(duplicate.status()).toBe(409);
  expect(backend.sql("select count(*) from created_tasks")[0][0]).toBe(before + 1);

  await page.getByRole("link", { name: "Chat", exact: true }).click();
  await expect(page.getByTestId("chat-thread")).toContainText(/Task created/i);
  await expect(page.getByTestId("chat-thread")).not.toContainText("Held for approval");
  await page.getByRole("link", { name: "Memory", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Memory inspector", exact: true })).toBeVisible();
  await expect(page.getByTestId("memory-list")).toBeVisible();
  await expect(page.getByText(/verify connected evidence/).first()).toBeVisible();
  await capture(page, "memory");
  const firstMemory = await (await request.get(`${backend.url}/agent/memory?session_id=live-workflow`)).json();
  const secondMemory = await (await request.get(`${backend.url}/agent/memory?session_id=live-workflow`)).json();
  expect(secondMemory.messages).toEqual(firstMemory.messages);
  expect(firstMemory.messages.filter((m: { content: string }) => m.content.includes("Task created"))).toHaveLength(1);

  await session(page, "live-empty");
  const empty = await (await request.get(`${backend.url}/agent/memory?session_id=live-empty`)).json();
  expect(empty.messages).toEqual([]);
  await page.getByRole("link", { name: "Runs", exact: true }).click();
  await expect(page).toHaveURL(/\/runs$/);
  await expect(page.getByRole("heading", { name: "Agent runs", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "No runs yet", exact: true })).toBeVisible();
  await expect(page.getByText("create a task to verify connected evidence", { exact: true })).toHaveCount(0);
  await page.reload();
  await expect(page.getByTestId("provider-label")).toContainText("Connected API mode");
  await expect(page.getByLabel("Session", { exact: true })).toHaveValue("live-empty");

  await backend.restart();
  const restored = await (await request.get(`${backend.url}/skills?session_id=live-workflow&run_id=${calculation.run_id}`)).json();
  expect(restored.activated).toEqual(evidence.activated);
  expect((await readRun(request, pending.run_id)).status).toBe("completed");
  expect((await request.post(`${backend.url}/approvals/${pending.approval.id}/approve`, { data: {} })).status()).toBe(409);
  expect(backend.sql("select count(*) from created_tasks")[0][0]).toBe(before + 1);
  writeProof(evidence, { status: completed.status, execution_status: completed.approval.execution_status, result: completed.approval.execution_result, run_id: pending.run_id }, firstMemory);
});

test("rejection, actual expiry and workspace denial produce zero task effects", async ({ page, request }) => {
  const before = backend.sql("select count(*) from created_tasks")[0][0];
  const rejected = await send(request, "live-denials", "create a task to reject this request");
  await page.goto(`/runs/${rejected.run_id}`); await session(page, "live-denials");
  await page.getByRole("button", { name: "Reject action", exact: true }).click();
  await expect(page.getByTestId("connected-decision-story")).toContainText(/not executed/i);
  expect((await readRun(request, rejected.run_id)).status).toBe("blocked");
  const denied = await send(request, "live-denials", "read ../outside.txt");
  expect(denied.status).toBe("blocked");
  expect(JSON.stringify(denied)).not.toContain("FORBIDDEN_OUTSIDE_SENTINEL");
  await page.goto(`/runs/${denied.run_id}`);
  await expect(page.getByTestId("connected-decision-story")).toContainText(/denied|blocked/i);

  await backend.restart(1);
  try {
    const expired = await send(request, "live-expiry", "create a task to expire this review");
    await expect.poll(async () => (await (await request.get(`${backend.url}/approvals/${expired.approval.id}`)).json()).status).toBe("expired");
    expect((await request.post(`${backend.url}/approvals/${expired.approval.id}/approve`, { data: {} })).status()).toBe(409);
    await page.goto(`/runs/${expired.run_id}`); await session(page, "live-expiry");
    await expect(page.getByTestId("connected-decision-story")).toContainText(/expired/i);
    expect((await readRun(request, expired.run_id)).status).toBe("blocked");
  } finally { await backend.restart(); }
  expect(backend.sql("select count(*) from created_tasks")[0][0]).toBe(before);
});

test("draft quick start, keyboard approval and unmatched requests stay truthful", async ({ page, request }) => {
  await page.goto("/chat"); await session(page, "live-draft");
  const before = backend.sql("select count(*) from agent_runs")[0][0];
  await page.getByRole("button", { name: "Draft an email to ops@example.test", exact: true }).click();
  await expect(page.getByLabel("Message the agent")).toHaveValue("Draft an email to ops@example.test");
  expect(backend.sql("select count(*) from agent_runs")[0][0]).toBe(before);
  const draft = await chat(page, "Draft an email to ops@example.test");
  expect(draft.skill_context.loaded_instruction_bodies[0].name).toBe("email-draft");
  await page.goto(`/runs/${draft.run_id}`);
  await page.getByRole("button", { name: "Approve action", exact: true }).focus();
  await page.keyboard.press("Space");
  await expect(page.getByTestId("connected-decision-story")).toContainText(/completed/i);
  const result = JSON.parse((await readRun(request, draft.run_id)).approval.execution_result);
  expect(result.status).toBe("drafted"); expect(result.sent).toBe(false); expect(result.to).toBe("ops@example.test");
  await page.getByRole("link", { name: "Chat", exact: true }).click();
  const unmatched = await chat(page, "hello friend");
  expect(unmatched.skill_context.loaded_instruction_bodies).toEqual([]);
  await expect(page.getByTestId("chat-thread")).toContainText(/no tool|no matching|could not|try|route/i);
});

test("real storage failure and a durable uncertain claim never appear successful", async ({ page, request }) => {
  const before = backend.sql("select count(*) from created_tasks")[0][0];
  const failed = await send(request, "live-failures", "create a task to test storage failure");
  backend.sql("CREATE TRIGGER live_fail_tasks BEFORE INSERT ON created_tasks BEGIN SELECT RAISE(ABORT, 'synthetic storage failure'); END");
  try {
    const response = await request.post(`${backend.url}/approvals/${failed.approval.id}/approve`, { data: {} });
    expect(response.status()).toBe(200);
    expect((await response.json()).approval.execution_status).toBe("failed");
  } finally { backend.sql("DROP TRIGGER live_fail_tasks"); }
  expect((await readRun(request, failed.run_id)).status).toBe("error");
  await page.goto(`/runs/${failed.run_id}`); await session(page, "live-failures");
  await expect(page.getByTestId("connected-decision-story")).toContainText(/failed/i);
  const uncertain = await send(request, "live-failures", "create a task to inspect an uncertain claim");
  // Explicit fault fixture: persisted claim models an interrupted dispatch. It
  // is not evidence that this browser test caused a tool-side process crash.
  backend.sql("UPDATE approvals SET status='approved', execution_status='claimed', execution_token='fixture-claim', execution_claimed_at=? WHERE id=?", [Date.now() / 1000, uncertain.approval.id]);
  await backend.restart();
  await page.goto(`/runs/${uncertain.run_id}`);
  await expect(page.getByTestId("connected-decision-story")).toContainText(/unconfirmed/i);
  await expect(page.getByRole("button", { name: "Approve action", exact: true })).toHaveCount(0);
  expect((await request.post(`${backend.url}/approvals/${uncertain.approval.id}/approve`, { data: {} })).status()).toBe(409);
  expect(backend.sql("select count(*) from created_tasks")[0][0]).toBe(before);
});

test("streamed runs preserve skill evidence and legacy history stays unknown", async ({ page, request }) => {
  const stream = await request.post(`${backend.url}/agent/chat/stream`, { data: { message: "calculate 9 + 2", session_id: "live-stream", mode: "approval_gated" } });
  expect(stream.status()).toBe(200); expect(await stream.text()).toContain("event: complete");
  const runs = await (await request.get(`${backend.url}/agent/runs?session_id=live-stream`)).json();
  const snapshot = await (await request.get(`${backend.url}/skills?session_id=live-stream&run_id=${runs.runs[0].id}`)).json();
  expect(snapshot.activated[0].name).toBe("calculator");
  const trace = JSON.stringify({ entries: [], spans: [], duration_ms: 0, total_steps: 0 });
  backend.sql("INSERT INTO agent_runs(id,query,response,mode,status,trace_json,cost_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)", ["legacy-live", "Legacy synthetic request", "Legacy recorded response", "free_running", "completed", trace, "{}", "2026-01-01 00:00:00", "2026-01-01 00:00:00"]);
  const legacy = await readRun(request, "legacy-live");
  expect(legacy.session_id).toBeNull(); expect(legacy.skill_context).toBeNull();
  await page.goto("/runs/legacy-live");
  await expect(page.getByText(/legacy|unavailable|unknown/i).first()).toBeVisible();
});

test("actual outage retry recovers and sample mode stops backend calls", async ({ page, request }) => {
  await send(request, "live-outage", "calculate 2 + 3");
  await page.goto("/runs"); await session(page, "live-outage");
  await backend.stop();
  try {
    await page.reload();
    await expect(page.getByTestId("error-state")).toContainText(/connect/i);
    await expect(page.getByTestId("run-list")).toHaveCount(0);
  } finally { await backend.start(); }
  await page.getByTestId("error-state").getByRole("button", { name: "Retry", exact: true }).click();
  await expect(page.getByTestId("run-list")).toBeVisible();
  await page.getByRole("button", { name: "Enter sample demo", exact: true }).first().click();
  await expect(page.getByTestId("provider-label")).toContainText("Interactive sample data");
  const calls: string[] = [];
  page.on("request", request => { if (request.url().startsWith(backend.url)) calls.push(request.url()); });
  await page.getByRole("link", { name: "Skills", exact: true }).click();
  await expect(page.getByTestId("skills-view")).toBeVisible();
  await page.getByRole("link", { name: "Chat", exact: true }).click();
  await expect(page.getByRole("button", { name: "What is 1450 * 32?", exact: true })).toBeVisible();
  expect(calls).toEqual([]);
});

for (const viewport of [{ width: 390, height: 844 }, { width: 768, height: 1024 }, { width: 1440, height: 900 }]) {
  test(`connected routes stay usable at ${viewport.width}x${viewport.height}`, async ({ page }) => {
    await page.setViewportSize(viewport); await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/chat"); await session(page, `live-visual-${viewport.width}`);
    await page.getByRole("link", { name: "Skip to content", exact: true }).focus();
    await page.keyboard.press("Enter");
    await expect(page.locator("#main-content")).toBeFocused();
    await page.keyboard.press("Tab");
    const calculation = await chat(page, "calculate 6 * 7");
    await expect(page.getByTestId("chat-thread")).toContainText("42");
    await expect(page.getByRole("combobox", { name: "Mode", exact: true })).toHaveValue("approval_gated");
    await expect(page.getByRole("combobox", { name: "Mode", exact: true }).getByRole("option", { name: "free-running", exact: true })).toBeDisabled();
    for (const route of ["/", "/runs", `/runs/${calculation.run_id}`, "/skills", "/memory", "/tools", "/approvals", "/setup"]) {
      await page.goto(route);
      await expect(page.getByTestId("provider-label")).toContainText("Connected API mode");
      await expect(page.getByTestId("error-state")).toHaveCount(0);
      const overflow = await page.evaluate(() => ({ width: innerWidth, document: document.documentElement.scrollWidth, elements: [...document.querySelectorAll("body *")].filter(el => el.getBoundingClientRect().right > innerWidth).slice(0, 8).map(el => ({ tag: el.tagName, right: el.getBoundingClientRect().right, class: el.className, text: el.textContent?.slice(0, 80) })) }));
      expect(overflow.document, `${route}: ${JSON.stringify(overflow)}`).toBeLessThanOrEqual(overflow.width);
      expect(await page.locator("nav .overflow-x-auto").evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true);
      if (route === "/") { await expect(page.getByRole("heading", { name: "Your requests. Real execution evidence.", exact: true })).toBeVisible(); await capture(page, `home-${viewport.width}`); }
      if (route === "/skills") { await expect(page.getByTestId("skills-view")).toBeVisible(); await capture(page, `skills-${viewport.width}`); }
      if (route === "/memory") await expect(page.getByTestId("memory-list")).toBeVisible();
    }
  });
}
