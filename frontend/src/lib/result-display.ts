/** Only recognized draft wire payloads receive a human-readable presentation. */
export function readableResult(raw: string): string {
  try {
    const value: unknown = JSON.parse(raw);
    if (!value || typeof value !== "object" || Array.isArray(value)) return raw;
    const draft = value as Record<string, unknown>;
    if (draft.status !== "drafted" || typeof draft.sent !== "boolean" || typeof draft.to !== "string" || typeof draft.subject !== "string" || typeof draft.body !== "string") return raw;
    return `Draft prepared for ${draft.to}.\n\nSubject: ${draft.subject}\n\n${draft.body}\n\n${draft.sent === false ? "Nothing was sent." : "Backend reports sent: true."}`;
  } catch { return raw; }
}
