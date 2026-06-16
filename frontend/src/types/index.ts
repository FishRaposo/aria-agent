// Type definitions mirroring the Hermes FastAPI response shapes.
// Source of truth: src/hermes/main.py + tracing.py + costs.py + store.py.

export type RunStatus =
  | "completed"
  | "pending_approval"
  | "blocked"
  | "error";

export type AgentMode = "free_running" | "approval_gated";

export type SpanType = "llm" | "tool" | "retrieval" | "decision" | "other";
export type SpanStatus = "ok" | "error";

/** A single canonical span (shared_core.tracing.Span.to_dict). */
export interface Span {
  span_id: string;
  trace_id: string;
  parent_span_id: string | null;
  name: string;
  span_type: SpanType;
  status: SpanStatus;
  start_ms: number;
  end_ms: number | null;
  attributes: Record<string, unknown>;
}

/** A human-readable trace entry (TraceLog.entries). */
export interface TraceEntry {
  step: number;
  type: "reasoning" | "decision" | "tool_call";
  content?: string;
  name?: string;
  tool?: string;
  params?: Record<string, unknown>;
  result?: string;
  latency_ms?: number;
  status?: SpanStatus;
}

/** TraceLog.summary() output. */
export interface TraceSummary {
  trace_id: string;
  total_steps: number;
  duration_ms: number;
  entries: TraceEntry[];
  spans: Span[];
}

/** CostTracker.summary() output (LLMMetrics + aliases). */
export interface CostSummary {
  total_requests: number;
  total_tokens: number;
  input_tokens: number;
  output_tokens: number;
  estimated_cost: number;
  average_latency_ms: number;
  p50_latency_ms: number;
  p95_latency_ms: number;
  p99_latency_ms: number;
  error_rate: number;
  cost_by_model: Record<string, number>;
  cost_by_prompt_version: Record<string, number>;
  // friendly aliases added by CostTracker.summary()
  total_cost: number;
  total_calls: number;
}

/** Normalised approval record (store.approval_to_dict). */
export interface Approval {
  id: string;
  run_id: string | null;
  action: string;
  parameters: Record<string, unknown>;
  status: "pending" | "approved" | "rejected" | "expired";
  reason: string | null;
  expires_at: number;
  decided_at: number | null;
  seconds_remaining: number;
}

/** A persisted agent run (run_store.save payload / get_run response). */
export interface AgentRun {
  id: string;
  query: string;
  response: string;
  mode: AgentMode;
  status: RunStatus;
  route: string | null;
  trace: TraceSummary;
  cost: CostSummary;
  created_at: number;
}

/** POST /agent/chat response (RunResult.to_dict + reply alias). */
export interface ChatResponse {
  run_id: string;
  query: string;
  response: string;
  reply: string;
  status: RunStatus;
  mode: AgentMode;
  route: string | null;
  approval: Approval | null;
  trace: TraceSummary;
  cost: CostSummary;
}

export interface ChatRequest {
  message: string;
  session_id?: string;
  mode?: AgentMode;
}

/** GET /tools entry (registry.list_tools). */
export interface ToolSpec {
  name: string;
  permission: "safe" | "requires_approval";
  description: string;
  schema: JsonSchema;
}

export interface JsonSchema {
  title?: string;
  type?: string;
  properties?: Record<string, JsonSchemaProperty>;
  required?: string[];
  [key: string]: unknown;
}

export interface JsonSchemaProperty {
  title?: string;
  type?: string;
  description?: string;
  default?: unknown;
  [key: string]: unknown;
}

/** POST /approvals/{id}/approve response. */
export interface ApprovalDecisionResponse {
  approval: Approval;
  result?: string;
  trace?: TraceSummary;
}

export interface RunListResponse {
  runs: AgentRun[];
}
export interface ApprovalListResponse {
  approvals: Approval[];
}
export interface ToolListResponse {
  tools: ToolSpec[];
}

export interface HealthResponse {
  status: string;
  service: string;
  dependencies?: Record<string, string>;
}

/** A conversation message rendered in the chat panel. */
export interface MemoryMessage {
  role: string;
  content: string;
}
