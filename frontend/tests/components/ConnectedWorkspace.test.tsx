import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import ChatPanel from "@/components/ChatPanel";
import ConnectedDecisionStory from "@/components/ConnectedDecisionStory";
import { getProviderMode, getSessionId, initializeClientSettings, resetDemo, setProviderMode, setSessionId } from "@/lib/demo-scenarios";
import { MOCK_RUNS } from "@/lib/mockData";
const health = { status: "ok", service: "aria", runtime: { agent_mode: "approval_gated", allowed_modes: ["approval_gated"], routing_mode: "keyword", skill_selection_mode: "automatic", persistence: "sqlite", skills_available: true } };
beforeEach(() => { sessionStorage.clear(); setSessionId("default"); setProviderMode("connected"); });
afterEach(() => { cleanup(); vi.restoreAllMocks(); setSessionId("default"); });
describe("connected workspace state", () => {
  it("rehydrates real history, uses session identity and locks strict mode", async () => {
    setSessionId("interview");
    const fetch = vi.fn(async (url: unknown) => ({ ok:true, json:async()=>String(url).includes("/health") ? health : {runs:[{...MOCK_RUNS[0],id:"saved-real",query:"Persisted request",response:"Persisted outcome",session_id:"interview"}]} }));
    global.fetch=fetch as unknown as typeof global.fetch;
    render(<ChatPanel/>);
    expect(await screen.findByText("Persisted outcome")).toBeInTheDocument();
    await waitFor(()=>expect(screen.getByLabelText("Mode")).toBeDisabled());
    expect(screen.getByText(/Strict deployment/)).toBeInTheDocument();
    expect(fetch.mock.calls.some(call=>String(call[0]).includes("session_id=interview"))).toBe(true);
    fireEvent.click(screen.getByRole("button",{name:"read ../outside.txt"}));
    expect(screen.getByLabelText("Message the agent")).toHaveValue("read ../outside.txt");
    expect(fetch.mock.calls.some(call=>String(call[0]).includes("/agent/chat"))).toBe(false);
  });
  it("restores provider and session preferences while reset only restores sample scenarios", () => {
    setProviderMode("sample");setSessionId("saved-session");
    const stored=sessionStorage.getItem("aria-console:v1");
    setProviderMode("connected");setSessionId("temporary");
    sessionStorage.setItem("aria-console:v1",stored!);
    initializeClientSettings();resetDemo();
    expect(getProviderMode()).toBe("sample");expect(getSessionId()).toBe("saved-session");
  });
  it("renders claimed execution as uncertain without enabled execution controls",()=>{
    render(<ConnectedDecisionStory run={{...MOCK_RUNS[0],status:"pending_approval",response:"Execution outcome unconfirmed",approval:{id:"claimed",run_id:MOCK_RUNS[0].id,action:"task_creator",parameters:{title:"Review"},status:"approved",execution_status:"claimed",reason:null,expires_at:99,decided_at:1,seconds_remaining:0}}}/>);
    expect(screen.getByRole("heading",{name:/outcome unconfirmed/i})).toBeInTheDocument();
    expect(screen.queryByRole("button",{name:"Approve action"})).not.toBeInTheDocument();
    expect(screen.getByText(/Reading this record never retries/)).toBeInTheDocument();
  });
});
