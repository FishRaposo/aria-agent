import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "@/lib/api";
import { createDemoState, transitionDemo, getDemoState, DRAFT_APPROVAL, DRAFT_RUN, EXPIRED_APPROVAL, resetDemo, setProviderMode, sampleChat, requestNewReview } from "@/lib/demo-scenarios";
beforeEach(() => { setProviderMode("sample"); resetDemo(); });
describe("single tab-local scenario state", () => {
  it("binds the reviewed parameters so altered actions cannot execute", () => {
    const state = createDemoState(0);
    state.approvals[0].parameters.subject = "Altered after review";
    expect(() => transitionDemo(state, DRAFT_APPROVAL, "approve", 1)).toThrow(/changed|binding/i);
  });
  it("executes approval once across approvals, runs, and fixture chat", async () => {
    const fetchSpy = vi.fn(); vi.stubGlobal("fetch", fetchSpy);
    await api.approve(DRAFT_APPROVAL);
    await expect(api.approve(DRAFT_APPROVAL)).rejects.toThrow(/approved/);
    expect(getDemoState().executions).toBe(1);
    expect((await api.getRun(DRAFT_RUN)).data.status).toBe("completed");
    expect(sampleChat("Draft an email to ops@example.test").approval?.status).toBe("approved");
    expect(fetchSpy).not.toHaveBeenCalled(); vi.unstubAllGlobals();
  });
  it("rejects unknown approval IDs instead of borrowing another action", () => {
    expect(() => transitionDemo(createDemoState(0), "missing", "approve", 1)).toThrow(/Unknown/);
  });
  it("keeps rejected and expired reviews unexecuted", () => {
    const rejected = transitionDemo(createDemoState(0), DRAFT_APPROVAL, "reject", 1);
    expect(rejected.executions).toBe(0);
    expect(() => transitionDemo(rejected, DRAFT_APPROVAL, "approve", 2)).toThrow(/rejected/);
    const expired = transitionDemo(createDemoState(0), DRAFT_APPROVAL, "approve", 240_000);
    expect(expired.executions).toBe(0);
    expect(expired.approvals[0].status).toBe("expired");
    expect(() => transitionDemo(expired, DRAFT_APPROVAL, "approve", 240_001)).toThrow(/expired/);
  });
  it("creates a new review without resurrecting an expired ID", () => {
    requestNewReview();
    expect(getDemoState().approvals.find(a => a.id === EXPIRED_APPROVAL)?.status).toBe("expired");
    expect(getDemoState().approvals.find(a => a.status === "pending")?.id).toBe("apr-new-review-1");
  });
  it("resets approvals, runs, execution counts, and rejects unsupported free text", async () => {
    await api.reject(DRAFT_APPROVAL); resetDemo();
    expect(getDemoState().approvals[0].status).toBe("pending");
    expect(getDemoState().runs[1].status).toBe("pending_approval");
    expect(getDemoState().executions).toBe(0);
    expect(() => sampleChat("What is 2 + 2?")).toThrow(/Preview limitation/);
  });
});

describe("review clock", () => {
  it("reports remaining review time rather than a fixed countdown", () => {
    vi.useFakeTimers();
    try {
      vi.setSystemTime(1000); resetDemo();
      vi.setSystemTime(61000);
      expect(getDemoState().approvals[0].seconds_remaining).toBe(180);
    } finally { vi.useRealTimers(); }
  });
});
