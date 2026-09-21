"use client";

import { ArrowLeft, Brain, GitBranch, Wrench } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ModeBadge, StatusBadge } from "@/components/Badges";
import CostSummaryCard from "@/components/CostSummaryCard";
import PageHeader from "@/components/PageHeader";
import { ErrorState, LoadingSkeleton } from "@/components/States";
import TraceTimeline from "@/components/TraceTimeline";
import { api, ApiError } from "@/lib/api";
import { formatClock, formatMs } from "@/lib/format";
import type { AgentRun, TraceEntry } from "@/types";

const ENTRY_ICON = {
  reasoning: Brain,
  decision: GitBranch,
  tool_call: Wrench,
} as const;

function EntryLine({ entry }: { entry: TraceEntry }) {
  const Icon = ENTRY_ICON[entry.type] ?? GitBranch;
  return (
    <div className="flex gap-3 py-2">
      <Icon className="mt-0.5 h-4 w-4 shrink-0 text-ink-500" />
      <div className="min-w-0 text-sm">
        <span className="mr-2 text-xs uppercase tracking-wide text-ink-600">
          {entry.type.replace("_", " ")}
        </span>
        {entry.type === "tool_call" ? (
          <span className="text-ink-200">
            <span className="mono text-emerald-300">{entry.tool}</span>
            {entry.result && (
              <span className="mono ml-2 text-ink-400">→ {entry.result}</span>
            )}
            {entry.status === "error" && (
              <span className="ml-2 text-rose-400">(error)</span>
            )}
          </span>
        ) : (
          <span className="text-ink-200">{entry.content || entry.name}</span>
        )}
      </div>
    </div>
  );
}

export default function RunDetailView({ runId }: { runId: string }) {
  const [run, setRun] = useState<AgentRun | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [demo, setDemo] = useState(false);
  const [demoForced, setDemoForced] = useState(false);
  const [demoReason, setDemoReason] = useState<string | undefined>();

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getRun(runId);
      setRun(res.data);
      setDemo(res.demo);
      setDemoForced(Boolean(res.demoForced));
      setDemoReason(res.demoReason);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? `${err.message} (HTTP ${err.status})`
          : err instanceof Error
          ? err.message
          : "Failed to load run"
      );
    } finally {
      setLoading(false);
    }
  }, [runId]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div>
      <Link
        href="/runs"
        className="mb-4 inline-flex items-center gap-1.5 text-sm text-ink-400 hover:text-ink-100"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to runs
      </Link>

      {loading ? (
        <LoadingSkeleton rows={4} />
      ) : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : run ? (
        <div className="space-y-6">
          <PageHeader
            title={`Run ${run.id}`}
            demo={demo}
            demoForced={demoForced}
            demoReason={demoReason}
            actions={
              <div className="flex items-center gap-2">
                <StatusBadge status={run.status} />
                <ModeBadge mode={run.mode} />
              </div>
            }
          />

          <div className="card">
            <div className="mb-1 text-xs uppercase tracking-wide text-ink-600">
              Query
            </div>
            <p className="mb-4 text-ink-100">{run.query}</p>
            <div className="mb-1 text-xs uppercase tracking-wide text-ink-600">
              Response
            </div>
            <p className="whitespace-pre-wrap text-ink-200">{run.response}</p>
            <div className="mt-4 flex flex-wrap gap-4 border-t border-ink-800 pt-3 text-xs text-ink-500">
              <span>route: {run.route ?? "—"}</span>
              <span>trace: {run.trace?.trace_id}</span>
              <span>duration: {formatMs(run.trace?.duration_ms)}</span>
              <span>created: {formatClock(run.created_at)}</span>
            </div>
          </div>

          <CostSummaryCard cost={run.cost} />

          <div className="grid gap-6 lg:grid-cols-5">
            <div className="lg:col-span-3">
              <h2 className="mb-3 text-sm font-semibold text-ink-200">
                Trace timeline
              </h2>
              <TraceTimeline trace={run.trace} />
            </div>
            <div className="lg:col-span-2">
              <h2 className="mb-3 text-sm font-semibold text-ink-200">
                Step log
              </h2>
              <div className="card divide-y divide-ink-800 py-0">
                {(run.trace?.entries ?? []).map((entry) => (
                  <EntryLine key={entry.step} entry={entry} />
                ))}
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
