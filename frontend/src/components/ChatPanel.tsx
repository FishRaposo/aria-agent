"use client";

import {
  Bot,
  Coins,
  CornerDownLeft,
  Gauge,
  Loader2,
  ShieldAlert,
  User,
  Wrench,
} from "lucide-react";
import Link from "next/link";
import { FIXTURE_PROMPTS, getProviderMode, getDemoState, setProviderMode, getSessionId, getConnectionEpoch, notifyConnectedChange } from "@/lib/demo-scenarios";
import { useDemoRevision } from "@/lib/use-demo";
import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { ModeBadge, StatusBadge } from "@/components/Badges";
import DemoBadge from "@/components/DemoBadge";
import PageHeader from "@/components/PageHeader";
import { api, ApiError } from "@/lib/api";
import { readableResult } from "@/lib/result-display";
import { formatCost, formatMs } from "@/lib/format";
import type { AgentMode, AgentRun, ChatResponse, HealthResponse, TraceEntry } from "@/types";

interface Turn {
  id: string;
  query: string;
  response: ChatResponse | null;
  /** True while this turn is awaiting the agent. */
  pending: boolean;
  /** Set when this turn errored (real HTTP error). */
  error?: string;
  demo?: boolean;
  demoForced?: boolean;
  demoReason?: string;
}

function toolCalls(entries: TraceEntry[]) {
  return entries.filter((e) => e.type === "tool_call");
}

export default function ChatPanel() {
  const revision = useDemoRevision();
  const sample = getProviderMode() === "sample";
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [mode, setMode] = useState<AgentMode>("approval_gated");
  const [busy, setBusy] = useState(false);
  const idRef = useRef(0);
  const [runtime, setRuntime] = useState<HealthResponse["runtime"]>();
  const [historyError, setHistoryError] = useState("");
  const [historyLoading, setHistoryLoading] = useState(false);
  const historySequence = useRef(0);
  const loadHistory = useCallback(async () => {
    if (getProviderMode() === "sample") return;
    const requestId = ++historySequence.current;
    setHistoryLoading(true);
    try {
      const history = await api.listRuns(50, getSessionId());
      if (requestId !== historySequence.current) return;
      const saved: Turn[] = [...history.data].reverse().map((run: AgentRun) => ({ id: run.id, query: run.query, pending: false, response: { run_id: run.id, query: run.query, response: run.response, reply: run.response, mode: run.mode, status: run.status, route: run.route, approval: run.approval || null, trace: run.trace, cost: run.cost } }));
      setTurns(previous => [...saved, ...previous.filter(turn => turn.pending || turn.error)]);
      setHistoryError("");
    } catch (error) { if (requestId === historySequence.current) setHistoryError(error instanceof Error ? error.message : "History unavailable"); }
    finally { if (requestId === historySequence.current) setHistoryLoading(false); }
  }, []);
  useEffect(() => { if (!sample) loadHistory(); return () => { historySequence.current += 1; }; }, [loadHistory, sample, revision]);
  useEffect(() => {
    if (sample) return;
    let active = true;
    api.health().then(response => { if (!active) return; setRuntime(response.data.runtime); if (response.data.runtime) setMode(response.data.runtime.agent_mode); }).catch(() => {});
    return () => { active = false; };
  }, [sample]);
  useEffect(() => { if (!sample) { const prompt = new URLSearchParams(window.location.search).get("prompt"); if (prompt) setInput(prompt); } }, [sample]);

  const send = async (retryMessage?: string) => {
    const message = (retryMessage ?? input).trim();
    if (!message || busy) return;
    const epoch = getConnectionEpoch();
    setInput("");
    setBusy(true);
    idRef.current += 1;
    const turnId = `t${idRef.current}`;
    setTurns((prev) => [
      ...prev,
      { id: turnId, query: message, response: null, pending: true },
    ]);

    try {
      const res = await api.chat({ message, mode, session_id: getSessionId() });
      if (epoch !== getConnectionEpoch()) return;
      setTurns((prev) =>
        prev.map((t) =>
          t.id === turnId
            ? {
                ...t,
                id: res.data.run_id,
                response: res.data,
                pending: false,
                demo: res.demo,
                demoForced: res.demoForced,
                demoReason: res.demoReason,
              }
            : t
        )
      );
      if (!res.demo) notifyConnectedChange();
    } catch (err) {
      if (epoch !== getConnectionEpoch()) return;
      const msg =
        err instanceof ApiError
          ? `${err.message} (HTTP ${err.status})`
          : err instanceof Error
          ? err.message
          : "Request failed";
      setTurns((prev) =>
        prev.map((t) =>
          t.id === turnId ? { ...t, pending: false, error: msg } : t
        )
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Chat with the agent"
        description={sample ? "Choose a fixture request to inspect a deterministic scenario. Free text requires a connected backend." : "Drive the reason-and-act loop. Each turn shows routing, tool calls, approval gating, and cost."}
        actions={
          <label className="flex items-center gap-2 text-sm text-ink-400">
            Mode
            <select
              disabled={!sample && (!runtime || runtime.allowed_modes.length === 1)}
              value={mode}
              onChange={(e) => setMode(e.target.value as AgentMode)}
              className="rounded-lg border border-ink-700 bg-ink-900 px-3 py-1.5 text-sm text-ink-100 outline-none focus:border-brand-500"
            >
              <option disabled={!sample && !runtime?.allowed_modes.includes("free_running")} value="free_running">free-running</option>
              <option value="approval_gated">approval-gated</option>
            </select>
          </label>
        }
      />

      {!sample && <div className="card mb-4 space-y-3"><p className="text-sm text-ink-200">Session: <span className="mono">{getSessionId()}</span></p><p className="text-xs text-ink-400">{runtime ? `${runtime.routing_mode} routing · ${runtime.skill_selection_mode} skill matching · ${runtime.persistence} persistence` : "Runtime metadata unavailable. Requests still report their own connection errors."}</p>{runtime?.allowed_modes.length === 1 && <p className="text-xs text-amber-200">Strict deployment: approval-gated mode is required by the backend.</p>}<p className="text-xs text-ink-400">Credential-free keyword routing supports tool requests, not open-ended conversation. Quick starts prepare a message; you choose when to send.</p><div className="flex flex-wrap gap-2" aria-label="Connected quick starts">{["What is 1450 * 32?", "Draft an email to ops@example.test", "Create a task review the incident", "read ../outside.txt"].map(prompt => <button key={prompt} className="btn-secondary text-xs" onClick={() => setInput(prompt)}>{prompt}</button>)}</div><button onClick={loadHistory} className="text-xs text-brand-200" disabled={historyLoading}>Refresh history</button>{historyError && <p role="status" className="text-xs text-rose-300">Saved history unavailable: {historyError}</p>}</div>}
      {sample && <div className="mb-4 flex flex-wrap gap-2" aria-label="Fixture prompts">{FIXTURE_PROMPTS.map(prompt => <button key={prompt} className="btn-secondary text-xs" onClick={() => setInput(prompt)}>{prompt}</button>)}</div>}
      <div
        data-testid="chat-thread"
        className="mb-4 min-h-[320px] space-y-5 rounded-xl border border-ink-800 bg-ink-900/40 p-5"
      >
        {turns.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <Bot className="mb-3 h-10 w-10 text-ink-400" />
            <p className="text-sm text-ink-400">
              Ask the agent something. Try{" "}
              <button
                className="text-brand-300 underline-offset-2 hover:underline"
                onClick={() => setInput("What is 1450 * 32?")}
              >
                a calculation
              </button>
              ,{" "}
              <button
                className="text-brand-300 underline-offset-2 hover:underline"
                onClick={() => setInput(sample ? "Inspect the unauthorized repository instruction" : "read ../outside.txt")}
              >
                an unauthorized action
              </button>
              , or{" "}
              <button
                className="text-brand-300 underline-offset-2 hover:underline"
                onClick={() => setInput("Draft an email to ops@example.test")}
              >
                an email draft
              </button>{" "}
              {sample ? "(the sample always enforces its permission boundary)." : "(live requests run against the configured backend boundary)."}
            </p>
          </div>
        ) : (
          turns.map((turn) => <TurnView key={turn.id} turn={turn} retry={() => send(turn.query)} busy={busy} />)
        )}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send();
        }}
        className="flex items-end gap-2"
      >
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          rows={2}
          placeholder="Message the agent…  (Enter to send, Shift+Enter for newline)"
          aria-label="Message the agent"
          className="flex-1 resize-none rounded-xl border border-ink-700 bg-ink-900 px-4 py-3 text-sm text-ink-100 placeholder:text-ink-400 outline-none focus:border-brand-500"
        />
        <button type="submit" className="btn-primary h-12" disabled={busy || !input.trim()}>
          {busy ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <CornerDownLeft className="h-4 w-4" />
          )}
          Send
        </button>
      </form>
    </div>
  );
}

function TurnView({ turn, retry, busy }: { turn: Turn; retry: () => void; busy: boolean }) {
  const original = turn.response;
  const current = turn.demo && original ? getDemoState().runs.find(run => run.id === original.run_id) : null;
  const res = current && original ? { ...original, response: current.response, reply: current.response, status: current.status, trace: current.trace } : original;
  const isWrite =
    res?.status === "pending_approval" ||
    (res?.trace.entries ?? []).some(
      (e) =>
        e.type === "tool_call" &&
        (e.tool === "email_draft" || e.tool === "task_creator")
    );

  return (
    <div className="space-y-3">
      {/* user message */}
      <div className="flex justify-end">
        <div className="flex max-w-[80%] items-start gap-2">
          <div className="rounded-2xl rounded-tr-sm bg-brand-600/90 px-4 py-2 text-sm text-white">
            {turn.query}
          </div>
          <span className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-ink-800 text-ink-300">
            <User className="h-4 w-4" />
          </span>
        </div>
      </div>

      {/* agent reply */}
      <div className="flex justify-start">
        <span className="mr-2 mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand-600/20 text-brand-300">
          <Bot className="h-4 w-4" />
        </span>
        <div className="w-full max-w-[88%] space-y-2">
          {turn.pending ? (
            <div className="inline-flex items-center gap-2 rounded-2xl rounded-tl-sm border border-ink-800 bg-ink-900 px-4 py-2.5 text-sm text-ink-400">
              <Loader2 className="h-4 w-4 animate-spin" />
              Agent is thinking…
            </div>
          ) : turn.error ? (
            <div className="rounded-2xl rounded-tl-sm border border-rose-500/30 bg-rose-500/10 px-4 py-2.5 text-sm text-rose-200">
              {turn.error}
              {getProviderMode() === "connected" && <div className="mt-3 flex flex-wrap gap-2"><button className="btn-secondary" onClick={retry} disabled={busy}>Retry</button><button className="btn-secondary" onClick={() => setProviderMode("sample")}>Enter sample demo</button></div>}
            </div>
          ) : res ? (
            <>
              <div className="rounded-2xl rounded-tl-sm border border-ink-800 bg-ink-900 px-4 py-2.5 text-sm text-ink-100">
                <div className="prose prose-invert prose-sm max-w-none prose-p:my-1">
                  <ReactMarkdown>{readableResult(res.reply || res.response)}</ReactMarkdown>
                </div>
              </div>

              {!turn.demo && <Link href={`/runs/${res.run_id}`} className="inline-block text-xs text-brand-200">Inspect execution timeline →</Link>}
              {/* loop / tool calls */}
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <StatusBadge status={res.status} />
                <ModeBadge mode={res.mode} />
                {res.route && (
                  <span className="rounded-full border border-ink-700 bg-ink-800/60 px-2 py-0.5 text-ink-400">
                    route: {res.route}
                  </span>
                )}
                {turn.demo && (
                  <DemoBadge
                    reason={turn.demoReason}
                    forced={turn.demoForced}
                  />
                )}
              </div>

              {toolCalls(res.trace.entries).map((tc, i) => (
                <div
                  key={i}
                  className="flex items-center gap-2 rounded-lg border border-ink-800 bg-ink-950/60 px-3 py-2 text-xs"
                >
                  <Wrench className="h-3.5 w-3.5 text-emerald-300" />
                  <span className="mono text-emerald-300">{tc.tool}</span>
                  <span className="mono truncate text-ink-400">
                    {JSON.stringify(tc.params)}
                  </span>
                  <span className="mono ml-auto shrink-0 text-ink-400">
                    {formatMs(tc.latency_ms)}
                  </span>
                </div>
              ))}

              {res.status === "pending_approval" && res.approval && (
                <div className="flex items-start gap-2 rounded-lg border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-xs text-amber-200">
                  <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>
                    Held for approval — id{" "}
                    <span className="mono">{res.approval.id}</span>. Resolve it
                    in the{" "}
                    <Link href="/approvals" className="underline">
                      Approval queue
                    </Link>
                    .
                  </span>
                </div>
              )}

              {/* cost line */}
              <div className="flex flex-wrap items-center gap-4 px-1 text-xs text-ink-400">
                <span className="inline-flex items-center gap-1">
                  <Coins className="h-3.5 w-3.5" />
                  {formatCost(res.cost.total_cost ?? res.cost.estimated_cost ?? 0)}
                </span>
                <span className="inline-flex items-center gap-1">
                  <Gauge className="h-3.5 w-3.5" />
                  {formatMs(res.trace.duration_ms)}
                </span>
                <span>{res.cost.total_calls ?? 0} LLM call(s)</span>
              </div>

              {turn.demo && isWrite && (
                <p className="px-1 text-xs italic text-amber-300/80">
                  demo — this write was simulated locally and not persisted.
                </p>
              )}
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}
