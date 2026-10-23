import { beforeEach } from "vitest";
import { setProviderMode } from "@/lib/demo-scenarios";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "@/lib/api";
import { mockBackendDown, mockHttpOk, mockHttpError } from "./utils";
import { MOCK_RUNS } from "@/lib/mockData";
beforeEach(() => setProviderMode("connected"));
afterEach(() => vi.restoreAllMocks());
describe("explicit connected provider", () => {
  it("surfaces network failure instead of substituting sample runs", async () => {
    mockBackendDown();
    await expect(api.listRuns()).rejects.toThrow(/connect|unreachable|fetch/i);
  });
  it("never simulates an approval when connected transport fails", async () => {
    mockBackendDown();
    await expect(api.approve("apr-77ce42aa10bd")).rejects.toThrow();
  });
  it("never fabricates a connected chat answer", async () => {
    mockBackendDown();
    await expect(api.chat({ message: "calculate 9 * 9" })).rejects.toThrow();
  });
  it("retains live response shapes", async () => {
    mockHttpOk({ runs: MOCK_RUNS });
    expect((await api.listRuns()).data).toEqual(MOCK_RUNS);
  });
  it("retains HTTP errors", async () => {
    mockHttpError(500, "boom");
    await expect(api.listRuns()).rejects.toBeInstanceOf(ApiError);
  });
});
