// Bundled mock data so every view is fully explorable with NO backend running.
// Shapes mirror the Hermes FastAPI responses exactly (see src/types/index.ts).

import type {
  AgentRun,
  Approval,
  ChatResponse,
  CostSummary,
  Span,
  ToolSpec,
  TraceEntry,
  TraceSummary,
} from "@/types";

const NOW = 1_718_460_000; // fixed epoch (≈ 2024-06-15) for deterministic demos

function cost(partial: Partial<CostSummary> = {}): CostSummary {
  const base: CostSummary = {
    total_requests: 2,
    total_tokens: 940,
    input_tokens: 720,
    output_tokens: 220,
    estimated_cost: 0.00231,
    average_latency_ms: 412.5,
    p50_latency_ms: 388.0,
    p95_latency_ms: 690.0,
    p99_latency_ms: 712.0,
    error_rate: 0.0,
    cost_by_model: { "gpt-4o-mini": 0.00231 },
    cost_by_prompt_version: { unversioned: 0.00231 },
    total_cost: 0.00231,
    total_calls: 2,
  };
  return { ...base, ...partial };
}

let spanCounter = 0;
function span(partial: Partial<Span> & { trace_id: string }): Span {
  spanCounter += 1;
  return {
    span_id: `span-${spanCounter}`,
    parent_span_id: null,
    name: "agent.run",
    span_type: "other",
    status: "ok",
    start_ms: 0,
    end_ms: 100,
    attributes: {},
    ...partial,
  };
}

function buildTrace(
  traceId: string,
  entries: TraceEntry[],
  spans: Span[],
  durationMs: number
): TraceSummary {
  return {
    trace_id: traceId,
    total_steps: entries.length,
    duration_ms: durationMs,
    entries,
    spans,
  };
}

// --- Run 1: calculator (safe tool, completed) -------------------------------
const trace1: TraceSummary = buildTrace(
  "trace-aa11",
  [
    { step: 1, type: "reasoning", content: "Processing query: what is 1450 * 32?" },
    {
      step: 2,
      type: "decision",
      name: "route",
      content: "tool=calculator via keyword",
    },
    {
      step: 3,
      type: "tool_call",
      tool: "calculator",
      params: { expression: "1450 * 32" },
      result: "46400",
      latency_ms: 0.42,
      status: "ok",
    },
  ],
  [
    span({ trace_id: "trace-aa11", name: "agent.run", span_type: "other", start_ms: 0, end_ms: 31.7 }),
    span({
      trace_id: "trace-aa11",
      name: "route",
      span_type: "decision",
      start_ms: 2.1,
      end_ms: 2.1,
      attributes: { tool: "calculator", strategy: "keyword", rationale: "matched 'calculate'" },
    }),
    span({
      trace_id: "trace-aa11",
      name: "tool.calculator",
      span_type: "tool",
      start_ms: 30.9,
      end_ms: 31.3,
      attributes: { tool: "calculator", params: { expression: "1450 * 32" }, result: "46400" },
    }),
  ],
  31.7
);

// --- Run 2: web_search (safe, completed, LLM router) ------------------------
const trace2: TraceSummary = buildTrace(
  "trace-bb22",
  [
    { step: 1, type: "reasoning", content: "Processing query: search for what is RAG" },
    { step: 2, type: "decision", name: "route", content: "tool=web_search via llm" },
    {
      step: 3,
      type: "tool_call",
      tool: "web_search",
      params: { query: "what is RAG" },
      result:
        "RAG (Retrieval-Augmented Generation) combines information retrieval with text generation.",
      latency_ms: 1.84,
      status: "ok",
    },
  ],
  [
    span({ trace_id: "trace-bb22", name: "agent.run", span_type: "other", start_ms: 0, end_ms: 642.0 }),
    span({
      trace_id: "trace-bb22",
      name: "route",
      span_type: "decision",
      start_ms: 610.0,
      end_ms: 610.0,
      attributes: { tool: "web_search", strategy: "llm", rationale: "intent: information retrieval" },
    }),
    span({
      trace_id: "trace-bb22",
      name: "tool.web_search",
      span_type: "tool",
      start_ms: 638.0,
      end_ms: 639.8,
      attributes: { tool: "web_search", params: { query: "what is RAG" } },
    }),
  ],
  642.0
);

// --- Run 3: email_draft requires approval (pending) -------------------------
const trace3: TraceSummary = buildTrace(
  "trace-cc33",
  [
    {
      step: 1,
      type: "reasoning",
      content: "Processing query: draft an email to ops@hermes.dev about the incident",
    },
    { step: 2, type: "decision", name: "route", content: "tool=email_draft via keyword" },
    {
      step: 3,
      type: "decision",
      name: "approval_pending",
      content: "email_draft requires approval (apr-77ce42aa10bd)",
    },
  ],
  [
    span({ trace_id: "trace-cc33", name: "agent.run", span_type: "other", start_ms: 0, end_ms: 14.2 }),
    span({
      trace_id: "trace-cc33",
      name: "route",
      span_type: "decision",
      start_ms: 3.0,
      end_ms: 3.0,
      attributes: { tool: "email_draft", strategy: "keyword" },
    }),
    span({
      trace_id: "trace-cc33",
      name: "approval_pending",
      span_type: "decision",
      start_ms: 12.0,
      end_ms: 12.0,
      attributes: { approval_id: "apr-77ce42aa10bd" },
    }),
  ],
  14.2
);

// --- Run 4: error (tool failure) --------------------------------------------
const trace4: TraceSummary = buildTrace(
  "trace-dd44",
  [
    { step: 1, type: "reasoning", content: "Processing query: read file ../../etc/passwd" },
    { step: 2, type: "decision", name: "route", content: "tool=file_reader via keyword" },
    {
      step: 3,
      type: "tool_call",
      tool: "file_reader",
      params: { filepath: "../../etc/passwd" },
      result: "error: path escapes the sandbox directory",
      latency_ms: 0.31,
      status: "error",
    },
  ],
  [
    span({ trace_id: "trace-dd44", name: "agent.run", span_type: "other", start_ms: 0, end_ms: 9.4 }),
    span({
      trace_id: "trace-dd44",
      name: "tool.file_reader",
      span_type: "tool",
      status: "error",
      start_ms: 8.0,
      end_ms: 8.3,
      attributes: {
        tool: "file_reader",
        params: { filepath: "../../etc/passwd" },
        result: "error: path escapes the sandbox directory",
      },
    }),
  ],
  9.4
);

export const MOCK_RUNS: AgentRun[] = [
  {
    id: "a1b2c3d4",
    query: "What is 1450 * 32?",
    response: "46400",
    mode: "free_running",
    status: "completed",
    route: "keyword",
    trace: trace1,
    cost: cost({
      total_requests: 0,
      total_calls: 0,
      total_tokens: 0,
      input_tokens: 0,
      output_tokens: 0,
      estimated_cost: 0,
      total_cost: 0,
      average_latency_ms: 0,
      p50_latency_ms: 0,
      p95_latency_ms: 0,
      p99_latency_ms: 0,
      cost_by_model: {},
      cost_by_prompt_version: {},
    }),
    created_at: NOW - 60,
  },
  {
    id: "e5f6a7b8",
    query: "Search for what is RAG",
    response:
      "RAG (Retrieval-Augmented Generation) combines information retrieval with text generation.",
    mode: "free_running",
    status: "completed",
    route: "llm",
    trace: trace2,
    cost: cost({
      estimated_cost: 0.00318,
      total_cost: 0.00318,
      cost_by_model: { "gpt-4o-mini": 0.00318 },
      cost_by_prompt_version: { "router-v2": 0.00318 },
      average_latency_ms: 305.0,
      p50_latency_ms: 305.0,
      p95_latency_ms: 305.0,
      p99_latency_ms: 305.0,
      total_requests: 1,
      total_calls: 1,
      total_tokens: 612,
      input_tokens: 540,
      output_tokens: 72,
    }),
    created_at: NOW - 240,
  },
  {
    id: "c9d0e1f2",
    query: "Draft an email to ops@hermes.dev about the incident",
    response:
      "Action 'email_draft' requires approval. Pending approval id: apr-77ce42aa10bd.",
    mode: "approval_gated",
    status: "pending_approval",
    route: "keyword",
    trace: trace3,
    cost: cost({
      total_requests: 0,
      total_calls: 0,
      total_tokens: 0,
      input_tokens: 0,
      output_tokens: 0,
      estimated_cost: 0,
      total_cost: 0,
      average_latency_ms: 0,
      p50_latency_ms: 0,
      p95_latency_ms: 0,
      p99_latency_ms: 0,
      cost_by_model: {},
      cost_by_prompt_version: {},
    }),
    created_at: NOW - 600,
  },
  {
    id: "0a1b2c3d",
    query: "Read file ../../etc/passwd",
    response: "Error executing 'file_reader': path escapes the sandbox directory",
    mode: "free_running",
    status: "error",
    route: "keyword",
    trace: trace4,
    cost: cost({
      total_requests: 0,
      total_calls: 0,
      total_tokens: 0,
      input_tokens: 0,
      output_tokens: 0,
      estimated_cost: 0,
      total_cost: 0,
      error_rate: 1.0,
      average_latency_ms: 0,
      p50_latency_ms: 0,
      p95_latency_ms: 0,
      p99_latency_ms: 0,
      cost_by_model: {},
      cost_by_prompt_version: {},
    }),
    created_at: NOW - 900,
  },
  {
    id: "4e5f6a7b",
    query: "Create a task to review the Q3 incident report",
    response:
      "Task created (id=8fa31c0b9e21): 'Review Q3 incident report' — follow up with on-call",
    mode: "free_running",
    status: "completed",
    route: "keyword",
    trace: buildTrace(
      "trace-ee55",
      [
        {
          step: 1,
          type: "reasoning",
          content: "Processing query: create a task to review the Q3 incident report",
        },
        { step: 2, type: "decision", name: "route", content: "tool=task_creator via keyword" },
        {
          step: 3,
          type: "tool_call",
          tool: "task_creator",
          params: { title: "Review Q3 incident report", description: "follow up with on-call" },
          result: "Task created (id=8fa31c0b9e21): 'Review Q3 incident report'",
          latency_ms: 2.6,
          status: "ok",
        },
      ],
      [
        span({ trace_id: "trace-ee55", name: "agent.run", span_type: "other", start_ms: 0, end_ms: 18.9 }),
        span({
          trace_id: "trace-ee55",
          name: "tool.task_creator",
          span_type: "tool",
          start_ms: 15.0,
          end_ms: 17.6,
          attributes: { tool: "task_creator", params: { title: "Review Q3 incident report" } },
        }),
      ],
      18.9
    ),
    cost: cost({
      total_requests: 0,
      total_calls: 0,
      total_tokens: 0,
      input_tokens: 0,
      output_tokens: 0,
      estimated_cost: 0,
      total_cost: 0,
      average_latency_ms: 0,
      p50_latency_ms: 0,
      p95_latency_ms: 0,
      p99_latency_ms: 0,
      cost_by_model: {},
      cost_by_prompt_version: {},
    }),
    created_at: NOW - 1500,
  },
];

export const MOCK_TOOLS: ToolSpec[] = [
  {
    name: "calculator",
    permission: "safe",
    description: "Safely evaluate an arithmetic expression (AST-based, no eval).",
    schema: {
      title: "CalculatorInput",
      type: "object",
      properties: {
        expression: {
          title: "Expression",
          type: "string",
          description: "Arithmetic expression to evaluate, e.g. '2 + 2 * 3'",
        },
      },
      required: ["expression"],
    },
  },
  {
    name: "web_search",
    permission: "safe",
    description: "Search the web (real when configured, deterministic mock offline).",
    schema: {
      title: "WebSearchInput",
      type: "object",
      properties: {
        query: { title: "Query", type: "string", description: "Search query string" },
      },
      required: ["query"],
    },
  },
  {
    name: "file_reader",
    permission: "safe",
    description: "Read a text file from the sandboxed, allowlisted directory.",
    schema: {
      title: "FileReaderInput",
      type: "object",
      properties: {
        filepath: {
          title: "Filepath",
          type: "string",
          description: "Path to a file, relative to the sandbox directory",
        },
      },
      required: ["filepath"],
    },
  },
  {
    name: "task_creator",
    permission: "requires_approval",
    description: "Persist a new task (write action — requires approval).",
    schema: {
      title: "TaskCreatorInput",
      type: "object",
      properties: {
        title: { title: "Title", type: "string", description: "Title of the task" },
        description: {
          title: "Description",
          type: "string",
          description: "Description of what needs to be done",
          default: "",
        },
      },
      required: ["title"],
    },
  },
  {
    name: "email_draft",
    permission: "requires_approval",
    description: "Draft a structured email — never sends (requires approval).",
    schema: {
      title: "EmailDraftInput",
      type: "object",
      properties: {
        recipient: { title: "Recipient", type: "string", description: "Email recipient address" },
        subject: { title: "Subject", type: "string", description: "Email subject line" },
        body: { title: "Body", type: "string", description: "Email body text" },
      },
      required: ["recipient", "subject", "body"],
    },
  },
];

export const MOCK_APPROVALS: Approval[] = [
  {
    id: "apr-77ce42aa10bd",
    run_id: "c9d0e1f2",
    action: "email_draft",
    parameters: {
      recipient: "ops@hermes.dev",
      subject: "Incident follow-up",
      body: "Summarising the Q3 incident and next steps for the on-call rotation.",
    },
    status: "pending",
    reason: null,
    expires_at: NOW + 240,
    decided_at: null,
    seconds_remaining: 240,
  },
  {
    id: "apr-1029384756ab",
    run_id: "4e5f6a7b",
    action: "task_creator",
    parameters: {
      title: "Rotate the staging API key",
      description: "Security flagged the key as stale during the audit.",
    },
    status: "pending",
    reason: null,
    expires_at: NOW + 95,
    decided_at: null,
    seconds_remaining: 95,
  },
  {
    id: "apr-abc123def456",
    run_id: "e5f6a7b8",
    action: "task_creator",
    parameters: { title: "Backfill billing dashboards", description: "" },
    status: "approved",
    reason: "Approved by on-call lead",
    expires_at: NOW - 300,
    decided_at: NOW - 320,
    seconds_remaining: 0,
  },
  {
    id: "apr-deadbeef0001",
    run_id: null,
    action: "email_draft",
    parameters: {
      recipient: "all-staff@hermes.dev",
      subject: "Company-wide outage",
      body: "Drafted broadcast — held for review.",
    },
    status: "rejected",
    reason: "Too broad an audience; route through comms first.",
    expires_at: NOW - 700,
    decided_at: NOW - 720,
    seconds_remaining: 0,
  },
];

export const MOCK_MEMORY: Record<string, { role: string; content: string }[]> = {
  default: [
    { role: "user", content: "What is 1450 * 32?" },
    { role: "system", content: "46400" },
    { role: "user", content: "Search for what is RAG" },
    {
      role: "system",
      content:
        "RAG (Retrieval-Augmented Generation) combines information retrieval with text generation.",
    },
    { role: "user", content: "Draft an email to ops@hermes.dev about the incident" },
    {
      role: "system",
      content: "Action 'email_draft' requires approval. Pending approval id: apr-77ce42aa10bd.",
    },
  ],
};

// Deterministic local "agent loop" for demo-mode chat (no backend).
export function mockChat(message: string, mode: "free_running" | "approval_gated"): ChatResponse {
  const lower = message.toLowerCase();
  const traceId = "trace-" + Math.random().toString(16).slice(2, 6);

  const reasoning: TraceEntry = {
    step: 1,
    type: "reasoning",
    content: `Processing query: ${message}`,
  };

  // Naive keyword routing mirroring the backend's KeywordRouter intent.
  let tool: string | null = null;
  let result = "";
  if (/[-+*/^]|\bcalc|\* |\bmultiply|\bplus\b/.test(lower) && /\d/.test(lower)) {
    tool = "calculator";
    result = "Computed result (demo): 46400";
  } else if (/search|look up|what is|who is/.test(lower)) {
    tool = "web_search";
    result =
      "An AI agent perceives its environment and takes actions to achieve goals by calling tools in a reason-and-act loop.";
  } else if (/email|draft|send/.test(lower)) {
    tool = "email_draft";
  } else if (/task|todo|remind|create/.test(lower)) {
    tool = "task_creator";
  } else if (/read|file/.test(lower)) {
    tool = "file_reader";
    result = "notes.txt: deployment checklist and rollback steps.";
  }

  const entries: TraceEntry[] = [reasoning];
  const spans: Span[] = [
    span({ trace_id: traceId, name: "agent.run", span_type: "other", start_ms: 0, end_ms: 120 }),
  ];

  if (!tool) {
    entries.push({
      step: 2,
      type: "decision",
      name: "route",
      content: "no tool matched — direct response",
    });
    return {
      run_id: traceId.replace("trace-", "run-"),
      query: message,
      response: "I processed your request but no tool was matched.",
      reply: "I processed your request but no tool was matched.",
      status: "completed",
      mode,
      route: "keyword",
      approval: null,
      trace: buildTrace(traceId, entries, spans, 120),
      cost: cost({
        total_requests: 1,
        total_calls: 1,
        estimated_cost: 0.00041,
        total_cost: 0.00041,
        total_tokens: 88,
        input_tokens: 64,
        output_tokens: 24,
        cost_by_model: { "gpt-4o-mini": 0.00041 },
      }),
    };
  }

  entries.push({
    step: 2,
    type: "decision",
    name: "route",
    content: `tool=${tool} via keyword`,
  });
  spans.push(
    span({
      trace_id: traceId,
      name: "route",
      span_type: "decision",
      start_ms: 4,
      end_ms: 4,
      attributes: { tool, strategy: "keyword" },
    })
  );

  const requiresApproval = tool === "email_draft" || tool === "task_creator";

  if (requiresApproval && mode === "approval_gated") {
    const approvalId = "apr-" + Math.random().toString(16).slice(2, 14);
    entries.push({
      step: 3,
      type: "decision",
      name: "approval_pending",
      content: `${tool} requires approval (${approvalId})`,
    });
    spans.push(
      span({
        trace_id: traceId,
        name: "approval_pending",
        span_type: "decision",
        start_ms: 10,
        end_ms: 10,
        attributes: { approval_id: approvalId },
      })
    );
    const response = `Action '${tool}' requires approval. Pending approval id: ${approvalId}.`;
    return {
      run_id: traceId.replace("trace-", "run-"),
      query: message,
      response,
      reply: response,
      status: "pending_approval",
      mode,
      route: "keyword",
      approval: {
        id: approvalId,
        run_id: traceId.replace("trace-", "run-"),
        action: tool,
        parameters: { note: "captured from demo chat" },
        status: "pending",
        reason: null,
        expires_at: NOW + 300,
        decided_at: null,
        seconds_remaining: 300,
      },
      trace: buildTrace(traceId, entries, spans, 14),
      cost: cost({
        total_requests: 0,
        total_calls: 0,
        estimated_cost: 0,
        total_cost: 0,
        total_tokens: 0,
        input_tokens: 0,
        output_tokens: 0,
        cost_by_model: {},
        cost_by_prompt_version: {},
      }),
    };
  }

  if (!result) {
    result =
      tool === "email_draft"
        ? '{"status":"drafted","sent":false,"note":"Draft only — never sends."}'
        : tool === "task_creator"
        ? "Task created (demo): captured your request."
        : "Done.";
  }

  entries.push({
    step: 3,
    type: "tool_call",
    tool,
    params: { input: message },
    result,
    latency_ms: 1.7,
    status: "ok",
  });
  spans.push(
    span({
      trace_id: traceId,
      name: `tool.${tool}`,
      span_type: "tool",
      start_ms: 100,
      end_ms: 101.7,
      attributes: { tool, params: { input: message }, result },
    })
  );

  return {
    run_id: traceId.replace("trace-", "run-"),
    query: message,
    response: result,
    reply: result,
    status: "completed",
    mode,
    route: "keyword",
    approval: null,
    trace: buildTrace(traceId, entries, spans, 122),
    cost: cost({
      total_requests: tool === "web_search" ? 1 : 0,
      total_calls: tool === "web_search" ? 1 : 0,
      estimated_cost: tool === "web_search" ? 0.00052 : 0,
      total_cost: tool === "web_search" ? 0.00052 : 0,
      total_tokens: tool === "web_search" ? 96 : 0,
      input_tokens: tool === "web_search" ? 70 : 0,
      output_tokens: tool === "web_search" ? 26 : 0,
      cost_by_model: tool === "web_search" ? { "gpt-4o-mini": 0.00052 } : {},
      cost_by_prompt_version: {},
    }),
  };
}
