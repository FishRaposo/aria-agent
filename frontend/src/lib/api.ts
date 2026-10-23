// Explicit providers: a failed connected request can never select sample data.
import type { AgentRun, Approval, ApprovalDecisionResponse, ApprovalListResponse, ChatRequest, ChatResponse, HealthResponse, MemoryMessage, RunListResponse, SkillsSnapshot, ToolListResponse, ToolSpec } from "@/types";
import { MOCK_TOOLS } from "./mockData";
import { decideDemo, getDemoState, getProviderMode, sampleChat, sampleSkills, tickDemo, getConnectionEpoch, notifyConnectedChange } from "./demo-scenarios";
export const DEMO_MODE = process.env.NEXT_PUBLIC_DEMO_MODE === "true";
export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); this.name = "ApiError"; }
}
export interface ApiResult<T> { data: T; demo: boolean; demoForced?: boolean; demoReason?: string }
const sample = <T,>(data: T): ApiResult<T> => ({ data, demo: true, demoForced: true, demoReason: "Interactive sample data — simulated locally, not persisted" });
const live = <T,>(data: T): ApiResult<T> => ({ data, demo: false });
async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const epoch = getConnectionEpoch();
  let response: Response;
  try { response = await fetch(`${API_BASE}${path}`, { ...options, headers: { "Content-Type": "application/json", ...options.headers } }); }
  catch { throw new Error("Could not connect to the ARIA backend. Retry or explicitly enter the sample demo."); }
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new ApiError(typeof body.detail === "string" ? body.detail : `API error: ${response.status}`, response.status);
  }
  const data = await response.json() as T;
  if (epoch !== getConnectionEpoch()) throw new Error("Request cancelled: provider or session changed.");
  return data;
}
const isSample = () => getProviderMode() === "sample";
class AriaApi {
  async listRuns(limit = 50, sessionId?: string): Promise<ApiResult<AgentRun[]>> {
    if (isSample()) { tickDemo(); return sample(getDemoState().runs.slice(0, limit)); }
    return live((await request<RunListResponse>(`/agent/runs?limit=${limit}${sessionId ? `&session_id=${encodeURIComponent(sessionId)}` : ""}`)).runs);
  }
  async getRun(id: string, sessionId?: string): Promise<ApiResult<AgentRun>> {
    if (!isSample()) {
      const run = await request<AgentRun>(`/agent/runs/${encodeURIComponent(id)}`);
      if (sessionId && run.session_id && run.session_id !== sessionId) throw new ApiError("This run belongs to another session. Select its session to inspect it.", 404);
      return live(run);
    }
    tickDemo(); const run = getDemoState().runs.find(r => r.id === id);
    if (!run) throw new ApiError(`Run '${id}' not found`, 404);
    return sample(run);
  }
  async chat(req: ChatRequest): Promise<ApiResult<ChatResponse>> {
    return isSample() ? sample(sampleChat(req.message)) : live(await request<ChatResponse>("/agent/chat", { method: "POST", body: JSON.stringify(req) }));
  }
  async listTools(): Promise<ApiResult<ToolSpec[]>> { return isSample() ? sample(MOCK_TOOLS) : live((await request<ToolListResponse>("/tools")).tools); }
  async getTool(name: string): Promise<ApiResult<ToolSpec>> {
    if (!isSample()) return live(await request<ToolSpec>(`/tools/${name}`));
    const tool = MOCK_TOOLS.find(t => t.name === name);
    if (!tool) throw new ApiError(`Tool '${name}' not found`, 404);
    return sample(tool);
  }
  async listApprovals(status?: string, sessionId?: string): Promise<ApiResult<Approval[]>> {
    if (isSample()) { tickDemo(); return sample(getDemoState().approvals.filter(a => !status || a.status === status)); }
    return live((await request<ApprovalListResponse>(`/approvals?${[status ? `status=${encodeURIComponent(status)}` : "", sessionId ? `session_id=${encodeURIComponent(sessionId)}` : ""].filter(Boolean).join("&")}`)).approvals);
  }
  async approve(id: string, reason?: string): Promise<ApiResult<ApprovalDecisionResponse>> {
    if (isSample()) return sample(decideDemo(id, true));
    const data = await request<ApprovalDecisionResponse>(`/approvals/${id}/approve`, { method: "POST", body: JSON.stringify({ reason: reason ?? null }) });
    notifyConnectedChange(); return live(data);
  }
  async reject(id: string, reason?: string): Promise<ApiResult<ApprovalDecisionResponse>> {
    if (isSample()) return sample(decideDemo(id, false));
    const data = await request<ApprovalDecisionResponse>(`/approvals/${id}/reject`, { method: "POST", body: JSON.stringify({ reason: reason ?? null }) });
    notifyConnectedChange(); return live(data);
  }
  async getSkills(sessionId = "default", runId?: string): Promise<ApiResult<SkillsSnapshot>> { return isSample() ? sample(sampleSkills()) : live(await request<SkillsSnapshot>(`/skills?session_id=${encodeURIComponent(sessionId)}${runId ? `&run_id=${encodeURIComponent(runId)}` : ""}`)); }
  async getMemory(sessionId = "default"): Promise<ApiResult<MemoryMessage[]>> {
    if (isSample()) return sample(getDemoState().runs.flatMap(run => [{ role: "user", content: run.query }, { role: "system", content: run.response }]));
    return live((await request<{ session_id: string; messages: MemoryMessage[] }>(`/agent/memory?session_id=${encodeURIComponent(sessionId)}&limit=50`)).messages);
  }
  async health(): Promise<ApiResult<HealthResponse>> {
    return isSample() ? sample({ status: "sample", service: "aria-agent-framework", dependencies: { database: "offline", redis: "offline" } }) : live(await request<HealthResponse>("/health"));
  }
}
export const api = new AriaApi();
