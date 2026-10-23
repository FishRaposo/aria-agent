"use client";

import { Activity, ChevronRight, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { ModeBadge, StatusBadge } from "@/components/Badges";
import CostSummaryCard from "@/components/CostSummaryCard";
import PageHeader from "@/components/PageHeader";
import RunCharts from "@/components/RunCharts";
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/States";
import { api, ApiError } from "@/lib/api";
import { useDemoRevision } from "@/lib/use-demo";
import { getProviderMode, getSessionId } from "@/lib/demo-scenarios";
import { formatCost, formatMs, timeAgo } from "@/lib/format";
import type { AgentRun, CostSummary } from "@/types";

function aggregate(runs: AgentRun[]): CostSummary {
  const totalCost = runs.reduce(
    (sum, r) => sum + (r.cost?.estimated_cost ?? 0),
    0
  );
  const totalTokens = runs.reduce((sum, r) => sum + (r.cost?.total_tokens ?? 0), 0);
  const totalCalls = runs.reduce((sum, r) => sum + (r.cost?.total_calls ?? 0), 0);
  const latencies = runs.map((r) => r.trace?.duration_ms ?? 0);
  const avgLatency =
    latencies.length > 0
      ? latencies.reduce((a, b) => a + b, 0) / latencies.length
      : 0;
  return {
    total_requests: totalCalls,
    total_tokens: totalTokens,
    input_tokens: 0,
    output_tokens: 0,
    estimated_cost: totalCost,
    average_latency_ms: avgLatency,
    p50_latency_ms: 0,
    p95_latency_ms: 0,
    p99_latency_ms: 0,
    error_rate: 0,
    cost_by_model: {},
    cost_by_prompt_version: {},
    total_cost: totalCost,
    total_calls: totalCalls,
  };
}

export default function RunsView() {
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const revision = useDemoRevision();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [demo, setDemo] = useState(false);
  const [demoForced, setDemoForced] = useState(false);
  const [demoReason, setDemoReason] = useState<string | undefined>();

  const requestSequence = useRef(0);
  const load = useCallback(async () => {
    const requestId = ++requestSequence.current;
    if (getProviderMode() !== "sample") setLoading(true);
    setError(null);
    try {
      const res = await api.listRuns(50, getSessionId());
      if (requestId !== requestSequence.current) return;
      setRuns(res.data);
      setDemo(res.demo);
      setDemoForced(Boolean(res.demoForced));
      setDemoReason(res.demoReason);
    } catch (err) {
      if (requestId !== requestSequence.current) return;
      setError(
        err instanceof ApiError
          ? `${err.message} (HTTP ${err.status})`
          : err instanceof Error
          ? err.message
          : "Failed to load runs"
      );
    } finally {
      if (requestId === requestSequence.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    return () => { requestSequence.current += 1; };
  }, [load, revision]);

  return (
    <div>
      <PageHeader
        title="Agent runs"
        description="Recent end-to-end runs with trace, status, route, and cost. Select a run to open its trace timeline."
        demo={demo}
        demoForced={demoForced}
        demoReason={demoReason}
        actions={
          <button onClick={load} className="btn-secondary" disabled={loading}>
            <RefreshCw className={loading ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
            Refresh
          </button>
        }
      />

      {loading ? (
        <LoadingSkeleton rows={5} />
      ) : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : runs.length === 0 ? (
        <EmptyState
          title="No runs yet"
          message="Start a conversation in the Chat view to produce the first agent run."
          icon={<Activity className="h-9 w-9" />}
        />
      ) : (
        <div className="space-y-8">
          {demo && <div className="outcome-panel"><p className="eyebrow text-brand-300">THREE REQUESTS. THREE OUTCOMES.</p><h2 className="mt-2">Follow a request to its execution boundary.</h2><p className="mt-2 text-sm text-ink-300">A calculation completes. A draft needs your review. An unauthorized send is denied.</p></div>}

          <div className="space-y-3" data-testid="run-list">
            {runs.map((run) => (
              <Link
                key={run.id}
                href={`/runs/${run.id}`}
                className="group flex items-center gap-4 rounded-xl border border-ink-800 bg-ink-900/50 p-4 transition-colors hover:border-brand-500/40 hover:bg-ink-900"
              >
                <div className="min-w-0 flex-1">
                  <div className="mb-1 flex flex-wrap items-center gap-2">
                    <span className="mono text-xs text-ink-400">{run.id}</span>
                    <StatusBadge status={run.status} />
                    <ModeBadge mode={run.mode} />
                    {run.route && (
                      <span className="rounded-full border border-ink-700 bg-ink-800/60 px-2 py-0.5 text-[11px] text-ink-400">
                        route: {run.route}
                      </span>
                    )}
                  </div>
                  <p className="truncate font-medium text-ink-100">{run.query}</p>
                  <p className="mt-0.5 truncate text-sm text-ink-400">
                    {run.response}
                  </p>
                </div>
                <div className="hidden shrink-0 text-right sm:block">
                  <div className="mono text-sm text-ink-200">
                    {formatCost(run.cost?.total_cost ?? run.cost?.estimated_cost ?? 0)}
                  </div>
                  <div className="mono text-xs text-ink-400">
                    {formatMs(run.trace?.duration_ms)}
                  </div>
                  <div className="mt-1 text-xs text-ink-400">
                    {demo ? "Fixture · fixed time" : timeAgo(run.created_at)}
                  </div>
                </div>
                <ChevronRight className="h-5 w-5 shrink-0 text-ink-400 transition-transform group-hover:translate-x-0.5 group-hover:text-brand-300" />
              </Link>
            ))}
          </div>
          <p className="text-xs text-ink-400">{demo ? "Illustrative fixture metrics. No model calls or charges in this preview." : "Reported backend metrics."}</p>
          <CostSummaryCard cost={aggregate(runs)} /><RunCharts runs={runs} />
        </div>
      )}
    </div>
  );
}
