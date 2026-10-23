import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import ConsoleBoundary from "@/components/ConsoleBoundary";
import DemoShell from "@/components/DemoShell";
import { setProviderMode, setSessionId } from "@/lib/demo-scenarios";
vi.mock("next/navigation", () => ({ usePathname: () => "/chat" }));
function EditableView() { const [draft, setDraft] = useState(""); return <input aria-label="Draft" value={draft} onChange={event => setDraft(event.target.value)}/>; }
function RouterState() {
  const [page, setPage] = useState("Chat route");
  return <div><button onClick={() => setPage("Memory route")}>Open memory route</button><p>{page}</p><ConsoleBoundary><EditableView/></ConsoleBoundary></div>;
}
beforeEach(() => { sessionStorage.clear(); setProviderMode("connected"); setSessionId("default"); });
describe("console route lifetime", () => {
  it("keeps the route tree mounted when the selected session changes", async () => {
    render(<DemoShell><RouterState/></DemoShell>);
    fireEvent.click(await screen.findByRole("button", { name: "Open memory route" }));
    expect(screen.getByText("Memory route")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Draft"), { target: { value: "Private old-session draft" } });
    fireEvent.change(screen.getByLabelText("Session"), { target: { value: "another-session" } });
    fireEvent.click(screen.getByRole("button", { name: "Use session" }));
    await waitFor(() => expect(screen.getByText("Memory route")).toBeInTheDocument());
    expect(screen.getByLabelText("Draft")).toHaveValue("");
  });
});
