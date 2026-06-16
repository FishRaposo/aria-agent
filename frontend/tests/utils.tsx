import { vi } from "vitest";

/**
 * Make global.fetch reject like a down backend so the api client's
 * demo-mode fallback engages. Returns the spy for assertions.
 */
export function mockBackendDown() {
  const spy = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
  global.fetch = spy as unknown as typeof fetch;
  return spy;
}

/**
 * Make global.fetch return a real HTTP error (e.g. 500) so error states
 * surface instead of falling back to mock data.
 */
export function mockHttpError(status = 500, detail = "Internal Server Error") {
  const spy = vi.fn().mockResolvedValue({
    ok: false,
    status,
    statusText: detail,
    json: async () => ({ detail }),
  });
  global.fetch = spy as unknown as typeof fetch;
  return spy;
}

/** Make global.fetch return a successful JSON payload. */
export function mockHttpOk(payload: unknown) {
  const spy = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => payload,
  });
  global.fetch = spy as unknown as typeof fetch;
  return spy;
}
