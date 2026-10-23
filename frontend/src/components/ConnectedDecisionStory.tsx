"use client";
import { useRef, useState } from "react";
import Link from "next/link";
import { Check, X } from "lucide-react";
import { api } from "@/lib/api";
import { readableResult } from "@/lib/result-display";
import { decisionNotice, executionLabel } from "@/lib/approval-outcome";
import type { AgentRun } from "@/types";

/** A read model of backend evidence; no fixture values or inferred execution counts. */
export default function ConnectedDecisionStory({ run }: { run: AgentRun }) {
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const noticeRef = useRef<HTMLDivElement>(null);
  const approval = run.approval;
  const calls = (run.trace?.entries || []).filter(entry => entry.type === "tool_call");
  const decisions = (run.trace?.entries || []).filter(entry => entry.type === "decision");
  const outcome = approval ? executionLabel(approval, false) : run.status === "completed" ? "Completed. Result recorded." : run.status === "blocked" ? "Blocked at the execution boundary." : run.status === "error" ? "Execution failed." : "Awaiting review.";
  const permission = approval ? "Requires human review. The proposal is bound to this run and its exact arguments." : run.status === "blocked" ? "A boundary rejected this request. Inspect the recorded decisions below." : "The backend evaluated the configured tool boundary. Inspect its recorded decisions.";
  const steps = [
    { title: "Request", body: run.query, detail: { session_id: run.session_id ?? "unknown (historical)", run_id: run.id } },
    { title: "Proposed tool", body: approval?.action || run.route || "No tool selected", detail: approval ? { action: approval.action, parameters: approval.parameters } : calls.map(call => ({ tool: call.tool, parameters: call.params })) },
    { title: "Permission", body: permission, detail: decisions },
    { title: "Approval", body: approval ? `Review: ${approval.status}. Execution: ${approval.execution_status || "not claimed"}.` : "No approval record attached to this run.", detail: approval ? { id: approval.id, status: approval.status, binding_hash: approval.binding_hash, expires_at: approval.expires_at, execution_status: approval.execution_status } : { approval: null } },
    { title: "Execution", body: readableResult(run.response), detail: approval ? { result: approval.execution_result, state: approval.execution_status, trace: approval.execution_trace } : calls },
  ];
  const decide = async (approve: boolean) => {
    if (!approval || busy) return;
    setBusy(true);
    try { const result = await (approve ? api.approve(approval.id) : api.reject(approval.id)); setNotice(decisionNotice(result.data, false)); }
    catch (error) { setNotice(error instanceof Error ? error.message : "Decision failed. Refresh to inspect the authoritative result."); }
    finally { setBusy(false); requestAnimationFrame(() => noticeRef.current?.focus({ preventScroll: true })); }
  };
  return <section aria-label="Execution decision story" className="space-y-5" data-testid="connected-decision-story">
    <div className="outcome-panel"><p className="eyebrow mb-2 text-brand-300">CONNECTED EXECUTION RECORD</p><h2>{outcome}</h2><p className="mt-2 text-sm text-ink-300">{approval?.execution_status === "claimed" ? "An execution was claimed, but no final outcome was persisted. Reconcile the effect before requesting another review. Reading this record never retries the tool." : "This timeline reads saved backend evidence. Review decisions and execution outcomes remain separate."}</p></div>
    <ol className="decision-timeline" aria-label="Request to execution timeline">{steps.map((step, index) => <li key={step.title} data-tone={run.status === "blocked" || run.status === "error" ? "denied" : approval?.status === "pending" ? "review" : "safe"}><span className="eyebrow text-ink-400">0{index + 1}</span><h3>{step.title}</h3><p className="whitespace-pre-wrap break-words">{step.body}</p><details><summary>Inspect {step.title.toLowerCase()}</summary><pre>{JSON.stringify(step.detail, null, 2)}</pre></details></li>)}</ol>
    {approval && <div className="card grid gap-5 md:grid-cols-2"><div className="min-w-0"><p className="eyebrow text-amber-300">EXACT ACTION FOR REVIEW</p><h3 className="mono mt-2 font-semibold text-ink-100">{approval.action}</h3><pre className="mono mt-4 max-w-full overflow-auto whitespace-pre-wrap break-words rounded-lg bg-ink-950 p-4 text-xs text-ink-200">{JSON.stringify(approval.parameters, null, 2)}</pre><p className="mt-3 text-xs text-ink-400">Approval applies to these unchanged arguments and this originating run. Skills cannot widen the tool boundary.</p></div><div><p className="text-sm text-ink-200">{executionLabel(approval, false)}</p><p className="mt-2 text-xs text-ink-400">{approval.reason}</p>{approval.status === "pending" && <div className="mt-5 flex flex-wrap gap-2"><button className="btn-primary" disabled={busy} onClick={() => decide(true)}><Check className="h-4 w-4"/>Approve action</button><button className="btn-secondary" disabled={busy} onClick={() => decide(false)}><X className="h-4 w-4"/>Reject action</button></div>}<div role="status" tabIndex={-1} ref={noticeRef} className="mt-4 text-sm text-brand-200">{notice}</div></div></div>}
    <div className="flex flex-wrap gap-4 text-xs text-brand-200"><Link href={`/skills?run_id=${encodeURIComponent(run.id)}`}>Inspect this run’s skills →</Link><Link href="/approvals">Approval queue →</Link><Link href="/memory">Conversation memory →</Link></div>
  </section>;
}
