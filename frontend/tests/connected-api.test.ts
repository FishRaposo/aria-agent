import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "@/lib/api";
import { setProviderMode } from "@/lib/demo-scenarios";
import { mockHttpOk } from "./utils";

beforeEach(() => setProviderMode("connected"));
describe("connected session API contracts", () => {
  it("filters history by the selected session without changing unfiltered callers", async () => {
    const fetch = mockHttpOk({ runs: [] });
    await api.listRuns(25, "review / one");
    expect(fetch.mock.calls[0][0]).toContain("/agent/runs?limit=25&session_id=review%20%2F%20one");
  });
  it("reads actual conversation memory rather than reconstructing runs", async () => {
    const fetch = mockHttpOk({ session_id: "one", messages: [{ role: "assistant", content: "A final outcome" }] });
    expect((await api.getMemory("one")).data).toEqual([{ role: "assistant", content: "A final outcome" }]);
    expect(fetch.mock.calls[0][0]).toContain("/agent/memory?session_id=one&limit=50");
  });
  it("reads the selected saved run's skill snapshot", async () => {
    const fetch = mockHttpOk({ catalog: [], activated: [], context_report: {} });
    await api.getSkills("one", "run / two");
    expect(fetch.mock.calls[0][0]).toContain("/skills?session_id=one&run_id=run%20%2F%20two");
  });
  it("clears a deep-linked run when its session differs from the selected session", async () => {
    mockHttpOk({ id: "other-run", session_id: "other" });
    await expect(api.getRun("other-run", "selected")).rejects.toThrow(/another session/);
  });
  it("filters approvals by session", async () => {
    const fetch = mockHttpOk({ approvals: [] });
    await api.listApprovals("pending", "one");
    expect(fetch.mock.calls[0][0]).toContain("/approvals?status=pending&session_id=one");
  });
  it("rejects results from a provider changed while the request was in flight", async () => {
    let resolve!: (value: unknown) => void;
    global.fetch = vi.fn(() => new Promise(r => { resolve = r; })) as typeof fetch;
    const response = api.listRuns();
    setProviderMode("sample");
    resolve({ ok: true, json: async () => ({ runs: [{ id: "private-live-run" }] }) });
    await expect(response).rejects.toThrow(/changed|cancelled|obsolete/i);
  });
});
