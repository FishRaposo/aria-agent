import { describe, expect, it } from "vitest";
import { readableResult } from "@/lib/result-display";
const draft = { status: "drafted", sent: false, to: "ops@example.test", subject: "Incident follow-up", body: "The service has recovered." };
describe("readable connected results", () => {
  it("explains a recognized draft without exposing a JSON wrapper", () => {
    const result = readableResult(JSON.stringify(draft));
    expect(result).toContain("Draft prepared for ops@example.test");
    expect(result).toContain("Subject: Incident follow-up");
    expect(result).toContain("The service has recovered.");
    expect(result).toContain("Nothing was sent.");
    expect(result).not.toContain('"status"');
  });
  it("does not claim nothing was sent when the backend reports true", () => {
    const result = readableResult(JSON.stringify({ ...draft, sent: true }));
    expect(result).not.toContain("Nothing was sent");
    expect(result).toContain("Backend reports sent: true");
  });
  it.each(["not JSON", "{broken", '{"status":"drafted","sent":false}', '{"status":"completed","result":42}', JSON.stringify({ ...draft, sent: "false" })])("preserves unknown or incomplete payloads: %s", raw => {
    expect(readableResult(raw)).toBe(raw);
  });
});
