import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "@/lib/api";
import { MOCK_RUNS, MOCK_TOOLS } from "@/lib/mockData";
import { mockBackendDown, mockHttpError, mockHttpOk } from "./utils";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("api client demo-mode fallback", () => {
  it("falls back to mock runs when the backend is unreachable", async () => {
    mockBackendDown();
    const res = await api.listRuns();
    expect(res.demo).toBe(true);
    expect(res.demoReason).toMatch(/unreachable/i);
    expect(res.data).toEqual(MOCK_RUNS);
  });

  it("returns live runs (demo=false) on a successful response", async () => {
    mockHttpOk({ runs: MOCK_RUNS });
    const res = await api.listRuns();
    expect(res.demo).toBe(false);
    expect(res.data).toHaveLength(MOCK_RUNS.length);
  });

  it("surfaces a real HTTP 500 as an ApiError (does not mask)", async () => {
    mockHttpError(500, "boom");
    await expect(api.listRuns()).rejects.toBeInstanceOf(ApiError);
  });

  it("surfaces a real HTTP 404 with its status code", async () => {
    mockHttpError(404, "Run 'x' not found");
    await expect(api.getRun("x")).rejects.toMatchObject({ status: 404 });
  });

  it("falls back to bundled tools when offline", async () => {
    mockBackendDown();
    const res = await api.listTools();
    expect(res.demo).toBe(true);
    expect(res.data.map((t) => t.name)).toEqual(
      MOCK_TOOLS.map((t) => t.name)
    );
  });

  it("runs the agent loop locally for chat when offline", async () => {
    mockBackendDown();
    const res = await api.chat({ message: "What is 2 * 21?" });
    expect(res.demo).toBe(true);
    expect(res.data.trace.entries.length).toBeGreaterThan(0);
    expect(res.data.status).toBe("completed");
  });

  it("produces a pending approval in approval-gated mode for a write tool", async () => {
    mockBackendDown();
    const res = await api.chat({
      message: "Draft an email to ops@aria.dev",
      mode: "approval_gated",
    });
    expect(res.data.status).toBe("pending_approval");
    expect(res.data.approval).not.toBeNull();
  });

  it("marks an approval decision as not persisted in demo mode", async () => {
    mockBackendDown();
    const res = await api.approve("apr-77ce42aa10bd", "ok");
    expect(res.demo).toBe(true);
    expect(res.demoReason).toMatch(/not persisted/i);
    expect(res.data.approval.status).toBe("approved");
  });
});
