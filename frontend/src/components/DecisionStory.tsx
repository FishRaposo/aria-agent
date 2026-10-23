"use client";
import { useRef, useState } from "react";
import Link from "next/link";
import { Check, X, RotateCcw } from "lucide-react";
import { decisionNotice } from "@/lib/approval-outcome";
import { api } from "@/lib/api";
import { DRAFT_RUN, DENIED_RUN, getDemoState, requestNewReview, expireDemo, resetDraftScenario } from "@/lib/demo-scenarios";
import type { AgentRun } from "@/types";
export default function DecisionStory({ run }: { run: AgentRun }) {
  const [busy, setBusy] = useState(false); const [notice, setNotice] = useState("");
  const resultRef = useRef<HTMLDivElement>(null);
  const state = getDemoState();
  const approval = [...state.approvals].reverse().find(a => a.run_id === run.id);
  const draft = run.id === DRAFT_RUN; const denied = run.id === DENIED_RUN;
  const outcome = denied ? "Denied. Nothing executed." : draft ? approval?.status === "approved" ? "Approved. Simulated exactly once." : approval?.status === "rejected" ? "Rejected. Not executed." : approval?.status === "expired" ? "Expired. Not executed." : "Paused at the approval boundary." : "Validated. Permitted. Completed.";
  const steps = [
    { title: "Request", body: denied ? "A repository instruction asks for an unauthorized send." : run.query, detail: denied ? { source: "untrusted repository data", grants_authority: false } : { source: "user", query: run.query } },
    { title: "Proposed tool", body: denied ? "email_send" : draft ? "email_draft" : "calculator", detail: denied ? { action: "email_send", recipient: "outside@example.test" } : draft ? approval?.parameters : { expression: "1450 * 32" } },
    { title: "Permission", body: denied ? "Not available. This tool is not registered." : draft ? "Requires review. Write action cannot run yet." : "Can run. Safe tool and valid schema.", detail: { schema_valid: !denied, permission: denied ? "denied" : draft ? "requires_approval" : "safe" } },
    { title: "Approval", body: denied ? "Cannot authorize an unavailable tool." : draft ? `Review status: ${approval?.status ?? "pending"}. Bound to this run and exact arguments.` : "Not required for this safe action.", detail: draft ? { id: approval?.id, status: approval?.status, single_use: true, expires_after: "4 minutes in this simulation" } : { approval_required: false } },
    { title: "Execution", body: denied ? "0 executions. No side effects." : draft ? approval?.status === "approved" ? "1 simulated draft. Sent: false." : "0 executions. No draft created." : "46,400. Deterministic calculation.", detail: { executed: !denied && (!draft || approval?.status === "approved"), simulated: true, sent: false } },
  ];
  const decide = async (approve: boolean) => {
    if (!approval || busy) return; setBusy(true);
    try { const response = await (approve ? api.approve(approval.id) : api.reject(approval.id)); setNotice(decisionNotice(response.data, response.demo)); }
    catch (error) { setNotice(error instanceof Error ? error.message : "Decision failed"); }
    finally { setBusy(false); requestAnimationFrame(() => resultRef.current?.focus({ preventScroll: true })); }
  };
  return <section aria-label="Execution decision story" className="space-y-5">
    <div className="outcome-panel" ref={resultRef} tabIndex={-1}><p className="eyebrow mb-2 text-brand-300">{denied ? "03 / UNAUTHORIZED ACTION" : draft ? "02 / HUMAN REVIEW" : "01 / SAFE CALCULATION"}</p><h2>{outcome}</h2><p className="mt-2 max-w-3xl text-sm text-ink-300">{denied ? "Repository text is data, not permission. The execution boundary checks the actual tool before it can run." : draft ? "A request is a proposal. Approval applies only to the unchanged action shown here, for one simulated execution." : "The schema validates the expression. The permission check allows the calculator. The result remains inspectable."}</p></div>
    <ol className="decision-timeline" aria-label="Request to execution timeline">{steps.map((step, i) => <li key={step.title} data-tone={denied && i > 1 ? "denied" : draft && i > 1 ? "review" : "safe"}><span className="eyebrow text-ink-400">0{i+1}</span><h3>{step.title}</h3><p>{step.body}</p><details><summary>Inspect {step.title.toLowerCase()}</summary><pre>{JSON.stringify(step.detail,null,2)}</pre></details></li>)}</ol>
    {draft && approval && <div className="card grid gap-5 md:grid-cols-2"><div><p className="eyebrow text-amber-300">EXACT ACTION FOR REVIEW</p><h3 className="mt-2 text-lg font-semibold">Create an incident follow-up draft</h3><p className="mt-2 text-sm text-ink-400">Draft only. The fixture has no sending capability. All arguments are bound to this review.</p><dl className="mt-4 space-y-3 text-sm approval-parameters">{Object.entries(approval.parameters).map(([key,value]) => <div key={key}><dt className="text-xs capitalize text-ink-400">{key}</dt><dd className="mt-1 text-ink-100">{String(value)}</dd></div>)}</dl></div><div className="rounded-lg border border-ink-700 bg-ink-950/50 p-5"><p className="text-xs text-ink-400">Review status</p><p className="mt-2 text-lg capitalize text-amber-200">{approval.status}</p><p className="mt-2 text-sm text-ink-300">{approval.status === "pending" ? "Review window: 4 minutes from the review request. Expiry blocks execution." : approval.reason}</p><div className="mt-5 flex flex-wrap gap-2">{approval.status === "pending" ? <><button className="btn-primary" disabled={busy} onClick={() => decide(true)}><Check className="h-4 w-4" />Approve draft</button><button className="btn-secondary" disabled={busy} onClick={() => decide(false)}><X className="h-4 w-4" />Reject draft</button><button className="mt-2 text-xs text-ink-300 underline" onClick={() => expireDemo(approval.id)}>Simulate expiry</button></> : <div className="space-y-4"><button className="btn-primary" disabled>{approval.status === "approved" ? "Approved draft" : "Review closed"}</button><br /><button className="btn-secondary" onClick={() => { if (approval.status === "expired") requestNewReview(); else resetDraftScenario(); setNotice("New review ready. Previous decision cannot execute again."); }}><RotateCcw className="h-4 w-4" />{approval.status === "expired" ? "Request new review" : "Reset this scenario"}</button></div>}</div><p className="mt-5 text-xs text-ink-400">Simulated executions in this demo: {state.executions}</p><p role="status" className="mt-3 text-xs text-brand-200">{notice}</p></div></div>}
    <div className="flex flex-wrap gap-5 text-xs text-brand-200"><Link href="/approvals">Inspect approval queue →</Link><Link href="/skills">Why did the skill load? →</Link><Link href="/setup">See the real setup case →</Link></div>
  </section>;
}
