"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, ShieldCheck } from "lucide-react";
import { api } from "@/lib/api";
import { getSessionId } from "@/lib/demo-scenarios";
import { useDemoRevision } from "@/lib/use-demo";
import { ErrorState, LoadingSkeleton } from "@/components/States";
import type { HealthResponse } from "@/types";
export default function ConnectedWorkspace() {
  const revision = useDemoRevision();
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const load = useCallback(async () => { setLoading(true); setError(""); try { setHealth((await api.health()).data); } catch (error) { setError(error instanceof Error ? error.message : "Connection failed"); } finally { setLoading(false); } }, []);
  useEffect(() => { load(); }, [load, revision]);
  return <section className="mb-10 space-y-5" aria-label="Connected workspace"><div className="outcome-panel"><p className="eyebrow flex items-center gap-2 text-emerald-300"><ShieldCheck className="h-4 w-4"/>LIVE WORKSPACE / {getSessionId()}</p><h2 className="mt-3">Your requests. Real execution evidence.</h2><p className="mt-3 max-w-3xl text-sm text-ink-300">Run a calculation, review a proposed write, or inspect a sandbox denial. The connected application stores the run, selected skills, approval outcome and conversation history.</p><div className="mt-5 flex flex-wrap gap-3"><Link href="/chat" className="btn-primary">Open connected chat<ArrowRight className="h-4 w-4"/></Link><Link href="/runs" className="btn-secondary">Saved runs</Link></div></div>{loading ? <LoadingSkeleton rows={1}/> : error ? <ErrorState message={error} onRetry={load}/> : <div className="grid gap-3 sm:grid-cols-3"><div className="stat-card"><p className="text-xs text-ink-400">Execution boundary</p><p className="mt-2 font-semibold text-ink-100">{health?.runtime?.agent_mode || "Not reported"}</p></div><div className="stat-card"><p className="text-xs text-ink-400">Routing / skill selection</p><p className="mt-2 font-semibold text-ink-100">{health?.runtime ? `${health.runtime.routing_mode} / ${health.runtime.skill_selection_mode}` : "Not reported"}</p></div><div className="stat-card"><p className="text-xs text-ink-400">Persistence</p><p className="mt-2 font-semibold text-ink-100">{health?.runtime?.persistence || "Not reported"}</p></div></div>}<div className="flex flex-wrap gap-2" aria-label="Live workflow quick starts">{[{label:"Calculate safely",prompt:"What is 1450 * 32?"},{label:"Review an email draft",prompt:"Draft an email to ops@example.test"},{label:"Test the file boundary",prompt:"read ../outside.txt"}].map(item=><Link key={item.label} href={`/chat?prompt=${encodeURIComponent(item.prompt)}`} className="btn-secondary">{item.label}</Link>)}</div><p className="text-xs text-ink-400">Quick starts prepare requests. Nothing executes until you send. The recruiter preview below uses separate, explicitly labeled sample data.</p></section>;
}
