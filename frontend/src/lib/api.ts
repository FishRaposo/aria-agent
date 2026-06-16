// Typed API client for the Hermes agent framework.
//
// Live-first with graceful demo-mode fallback:
//  - Each call tries the real backend at NEXT_PUBLIC_API_URL.
//  - A *network* failure (backend down / unreachable) falls back to bundled
//    mock data and flags `demo: true` so the UI can show a "Demo mode" badge.
//  - A real HTTP 4xx/5xx is surfaced as an ApiError (never masked).

import type {
  Approval,
  ApprovalDecisionResponse,
  ApprovalListResponse,
  ChatRequest,
  ChatResponse,
  AgentRun,
  HealthResponse,
  MemoryMessage,
  RunListResponse,
  ToolListResponse,
  ToolSpec,
} from "@/types";
import {
  MOCK_APPROVALS,
  MOCK_MEMORY,
  MOCK_RUNS,
  MOCK_TOOLS,
  mockChat,
} from "@/lib/mockData";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/** A real HTTP error returned by the backend (4xx/5xx) — surfaced, not masked. */
export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/** Result wrapper: carries the payload plus whether mock data was used. */
export interface ApiResult<T> {
  data: T;
  demo: boolean;
  /** When in demo mode, the underlying reason (e.g. "backend unreachable"). */
  demoReason?: string;
}

function live<T>(data: T): ApiResult<T> {
  return { data, demo: false };
}
function demo<T>(data: T, reason: string): ApiResult<T> {
  return { data, demo: true, demoReason: reason };
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<{ ok: true; data: T } | { ok: false; networkError: true }> {
  const url = `${API_BASE}${path}`;
  let response: Response;
  try {
    response = await fetch(url, {
      headers: { "Content-Type": "application/json", ...options.headers },
      ...options,
    });
  } catch {
    // Network-level failure (DNS, connection refused, CORS at network layer).
    return { ok: false, networkError: true };
  }

  if (!response.ok) {
    // Real HTTP error — surface it, do NOT fall back to mock data.
    const body = await response
      .json()
      .catch(() => ({ detail: response.statusText }));
    throw new ApiError(
      body.detail || `API error: ${response.status}`,
      response.status
    );
  }

  const data = (await response.json()) as T;
  return { ok: true, data };
}

const NETWORK_REASON = "backend unreachable — showing bundled demo data";

class HermesApi {
  async listRuns(limit = 50): Promise<ApiResult<AgentRun[]>> {
    const res = await request<RunListResponse>(`/agent/runs?limit=${limit}`);
    if (res.ok) return live(res.data.runs);
    return demo(MOCK_RUNS, NETWORK_REASON);
  }

  async getRun(runId: string): Promise<ApiResult<AgentRun>> {
    const res = await request<AgentRun>(`/agent/runs/${runId}`);
    if (res.ok) return live(res.data);
    const found = MOCK_RUNS.find((r) => r.id === runId);
    if (!found) throw new ApiError(`Run '${runId}' not found`, 404);
    return demo(found, NETWORK_REASON);
  }

  async chat(req: ChatRequest): Promise<ApiResult<ChatResponse>> {
    const res = await request<ChatResponse>(`/agent/chat`, {
      method: "POST",
      body: JSON.stringify(req),
    });
    if (res.ok) return live(res.data);
    const reply = mockChat(req.message, req.mode || "free_running");
    return demo(reply, "backend unreachable — running the agent loop locally");
  }

  async listTools(): Promise<ApiResult<ToolSpec[]>> {
    const res = await request<ToolListResponse>(`/tools`);
    if (res.ok) return live(res.data.tools);
    return demo(MOCK_TOOLS, NETWORK_REASON);
  }

  async getTool(name: string): Promise<ApiResult<ToolSpec>> {
    const res = await request<ToolSpec>(`/tools/${name}`);
    if (res.ok) return live(res.data);
    const found = MOCK_TOOLS.find((t) => t.name === name);
    if (!found) throw new ApiError(`Tool '${name}' not found`, 404);
    return demo(found, NETWORK_REASON);
  }

  async listApprovals(status?: string): Promise<ApiResult<Approval[]>> {
    const qs = status ? `?status=${encodeURIComponent(status)}` : "";
    const res = await request<ApprovalListResponse>(`/approvals${qs}`);
    if (res.ok) return live(res.data.approvals);
    const filtered = status
      ? MOCK_APPROVALS.filter((a) => a.status === status)
      : MOCK_APPROVALS;
    return demo(filtered, NETWORK_REASON);
  }

  async approve(
    id: string,
    reason?: string
  ): Promise<ApiResult<ApprovalDecisionResponse>> {
    const res = await request<ApprovalDecisionResponse>(
      `/approvals/${id}/approve`,
      { method: "POST", body: JSON.stringify({ reason: reason ?? null }) }
    );
    if (res.ok) return live(res.data);
    return demo(this.mockDecision(id, true, reason), "demo — not persisted");
  }

  async reject(
    id: string,
    reason?: string
  ): Promise<ApiResult<ApprovalDecisionResponse>> {
    const res = await request<ApprovalDecisionResponse>(
      `/approvals/${id}/reject`,
      { method: "POST", body: JSON.stringify({ reason: reason ?? null }) }
    );
    if (res.ok) return live(res.data);
    return demo(this.mockDecision(id, false, reason), "demo — not persisted");
  }

  private mockDecision(
    id: string,
    approved: boolean,
    reason?: string
  ): ApprovalDecisionResponse {
    const base = MOCK_APPROVALS.find((a) => a.id === id) ?? MOCK_APPROVALS[0];
    const decided: Approval = {
      ...base,
      id,
      status: approved ? "approved" : "rejected",
      reason: reason ?? (approved ? "Approved (demo)" : "Rejected (demo)"),
      decided_at: Math.floor(Date.now() / 1000),
      seconds_remaining: 0,
    };
    return {
      approval: decided,
      ...(approved
        ? { result: "Tool executed (demo) — not persisted." }
        : {}),
    };
  }

  /** Conversation memory for a session (no backend route; demo-only inspector). */
  async getMemory(
    sessionId = "default"
  ): Promise<ApiResult<MemoryMessage[]>> {
    // The backend persists memory but exposes no read route, so we derive it
    // from recent runs when live, and fall back to bundled memory in demo mode.
    const res = await request<RunListResponse>(`/agent/runs?limit=50`);
    if (res.ok) {
      const messages: MemoryMessage[] = [];
      const ordered = [...res.data.runs].sort(
        (a, b) => a.created_at - b.created_at
      );
      for (const run of ordered) {
        messages.push({ role: "user", content: run.query });
        if (run.response)
          messages.push({ role: "system", content: run.response });
      }
      return live(messages);
    }
    return demo(MOCK_MEMORY[sessionId] ?? MOCK_MEMORY.default, NETWORK_REASON);
  }

  async health(): Promise<ApiResult<HealthResponse>> {
    const res = await request<HealthResponse>(`/health`);
    if (res.ok) return live(res.data);
    return demo(
      {
        status: "offline",
        service: "hermes-agent-framework",
        dependencies: { database: "offline", redis: "offline" },
      },
      NETWORK_REASON
    );
  }
}

export const api = new HermesApi();
