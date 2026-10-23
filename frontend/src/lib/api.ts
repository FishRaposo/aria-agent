// Explicit providers: a failed connected request can never select sample data.
import type { AgentRun, Approval, ApprovalDecisionResponse, ApprovalListResponse, ChatRequest, ChatResponse, HealthResponse, MemoryMessage, RunListResponse, SkillsSnapshot, ToolListResponse, ToolSpec } from "@/types";
import { MOCK_TOOLS } from "./mockData";
import { decideDemo, getDemoState, getProviderMode, sampleChat, sampleSkills, tickDemo } from "./demo-scenarios";
export const DEMO_MODE = process.env.NEXT_PUBLIC_DEMO_MODE === "true";
export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); this.name = "ApiError"; }
}
export interface ApiResult<T> { data: T; demo: boolean; demoForced?: boolean; demoReason?: string }
const sample = <T,>(data: T): ApiResult<T> => ({ data, demo: true, demoForced: true, demoReason: "Interactive sample data — simulated locally, not persisted" });
const live = <T,>(data: T): ApiResult<T> => ({ data, demo: false });
async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response;
  try { response = await fetch(`${API_BASE}${path}`, { ...options, headers: { "Content-Type": "application/json", ...options.headers } }); }
  catch { throw new Error("Could not connect to the ARIA backend. Retry or explicitly enter the sample demo."); }
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new ApiError(typeof body.detail === "string" ? body.detail : `API error: ${response.status}`, response.status);
  }
  return response.json() as Promise<T>;
}
const isSample = () => getProviderMode() === "sample";
class AriaApi {
  async listRuns(limit = 50): Promise<ApiResult<AgentRun[]>> {
    if (isSample()) { tickDemo(); return sample(getDemoState().runs.slice(0, limit)); }
    return live((await request<RunListResponse>(`/agent/runs?limit=${limit}`)).runs);
  }
  async getRun(id: string): Promise<ApiResult<AgentRun>> {
    if (!isSample()) return live(await request<AgentRun>(`/agent/runs/${id}`));
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
  async listApprovals(status?: string): Promise<ApiResult<Approval[]>> {
    if (isSample()) { tickDemo(); return sample(getDemoState().approvals.filter(a => !status || a.status === status)); }
    return live((await request<ApprovalListResponse>(`/approvals${status ? `?status=${encodeURIComponent(status)}` : ""}`)).approvals);
  }
  async approve(id: string, reason?: string): Promise<ApiResult<ApprovalDecisionResponse>> {
    return isSample() ? sample(decideDemo(id, true)) : live(await request<ApprovalDecisionResponse>(`/approvals/${id}/approve`, { method: "POST", body: JSON.stringify({ reason: reason ?? null }) }));
  }
  async reject(id: string, reason?: string): Promise<ApiResult<ApprovalDecisionResponse>> {
    return isSample() ? sample(decideDemo(id, false)) : live(await request<ApprovalDecisionResponse>(`/approvals/${id}/reject`, { method: "POST", body: JSON.stringify({ reason: reason ?? null }) }));
  }
  async getSkills(): Promise<ApiResult<SkillsSnapshot>> { return isSample() ? sample(sampleSkills()) : live(await request<SkillsSnapshot>("/skills")); }
  async getMemory(_sessionId = "default"): Promise<ApiResult<MemoryMessage[]>> {
    const runs = (await this.listRuns()).data;
    const messages = runs.flatMap(run => [{ role: "user", content: run.query }, { role: "system", content: run.response }]);
    return isSample() ? sample(messages) : live(messages);
  }
  async health(): Promise<ApiResult<HealthResponse>> {
    return isSample() ? sample({ status: "sample", service: "aria-agent-framework", dependencies: { database: "offline", redis: "offline" } }) : live(await request<HealthResponse>("/health"));
  }
}
export const api = new AriaApi();
