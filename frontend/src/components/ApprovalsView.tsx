"use client";

import { Check, Clock, RefreshCw, ShieldCheck, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import clsx from "clsx";
import { ApprovalStatusBadge } from "@/components/Badges";
import PageHeader from "@/components/PageHeader";
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/States";
import { api, ApiError } from "@/lib/api";
import { durationLabel } from "@/lib/format";
import type { Approval } from "@/types";

const FILTERS = [
  { value: "", label: "All" },
  { value: "pending", label: "Pending" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
  { value: "expired", label: "Expired" },
];

export default function ApprovalsView() {
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [demo, setDemo] = useState(false);
  const [demoReason, setDemoReason] = useState<string | undefined>();
  const [filter, setFilter] = useState("");
  const [acting, setActing] = useState<Record<string, boolean>>({});
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.listApprovals(filter || undefined);
      setApprovals(res.data);
      setDemo(res.demo);
      setDemoReason(res.demoReason);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? `${err.message} (HTTP ${err.status})`
          : err instanceof Error
          ? err.message
          : "Failed to load approvals"
      );
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    load();
  }, [load]);

  const decide = async (id: string, approve: boolean) => {
    setActing((p) => ({ ...p, [id]: true }));
    setNotice(null);
    try {
      const res = approve ? await api.approve(id) : await api.reject(id);
      setApprovals((prev) =>
        prev.map((a) => (a.id === id ? res.data.approval : a))
      );
      if (res.demo) {
        setNotice("demo — decision simulated locally and not persisted.");
      } else if (approve && res.data.result) {
        setNotice(`Approved and executed: ${res.data.result}`);
      }
    } catch (err) {
      setError(
        err instanceof ApiError
          ? `${err.message} (HTTP ${err.status})`
          : err instanceof Error
          ? err.message
          : "Decision failed"
      );
    } finally {
      setActing((p) => ({ ...p, [id]: false }));
    }
  };

  const pendingCount = approvals.filter((a) => a.status === "pending").length;

  return (
    <div>
      <PageHeader
        title="Approval queue"
        description="Human-in-the-loop gate for risky write actions. Approve to execute the tool, or reject to cancel."
        demo={demo}
        demoReason={demoReason}
        actions={
          <button onClick={load} className="btn-secondary" disabled={loading}>
            <RefreshCw className={loading ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
            Refresh
          </button>
        }
      />

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-1.5">
          {FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => setFilter(f.value)}
              className={clsx(
                "rounded-lg px-3 py-1.5 text-xs font-medium transition-colors",
                filter === f.value
                  ? "bg-brand-600/20 text-brand-200"
                  : "text-ink-400 hover:bg-ink-800/60 hover:text-ink-200"
              )}
            >
              {f.label}
            </button>
          ))}
        </div>
        {pendingCount > 0 && (
          <span className="text-xs text-amber-300">
            {pendingCount} awaiting decision
          </span>
        )}
      </div>

      {notice && (
        <div className="mb-4 rounded-lg border border-brand-500/30 bg-brand-500/10 px-4 py-2.5 text-sm text-brand-200">
          {notice}
        </div>
      )}

      {loading ? (
        <LoadingSkeleton rows={3} />
      ) : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : approvals.length === 0 ? (
        <EmptyState
          title="No approvals"
          message={
            filter
              ? `No approvals with status "${filter}".`
              : "The queue is empty. Risky tool calls in approval-gated mode will appear here."
          }
          icon={<ShieldCheck className="h-9 w-9" />}
        />
      ) : (
        <div className="space-y-3" data-testid="approval-list">
          {approvals.map((a) => (
            <div key={a.id} className="card">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="mb-1 flex flex-wrap items-center gap-2">
                    <span className="mono font-semibold text-ink-100">
                      {a.action}
                    </span>
                    <ApprovalStatusBadge status={a.status} />
                    {a.run_id && (
                      <a
                        href={`/runs/${a.run_id}`}
                        className="mono text-xs text-brand-300 hover:underline"
                      >
                        run {a.run_id}
                      </a>
                    )}
                  </div>
                  <pre className="mono max-w-full overflow-x-auto rounded-lg border border-ink-800 bg-ink-950/50 p-2.5 text-xs text-ink-300">
                    {JSON.stringify(a.parameters, null, 2)}
                  </pre>
                  {a.reason && (
                    <p className="mt-2 text-xs text-ink-400">
                      Reason: {a.reason}
                    </p>
                  )}
                </div>

                <div className="flex shrink-0 flex-col items-end gap-2">
                  {a.status === "pending" ? (
                    <>
                      <span className="inline-flex items-center gap-1 text-xs text-ink-500">
                        <Clock className="h-3.5 w-3.5" />
                        {durationLabel(a.seconds_remaining)} left
                      </span>
                      <div className="flex gap-2">
                        <button
                          onClick={() => decide(a.id, true)}
                          disabled={acting[a.id]}
                          className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-emerald-500 disabled:opacity-50"
                        >
                          <Check className="h-3.5 w-3.5" />
                          Approve
                        </button>
                        <button
                          onClick={() => decide(a.id, false)}
                          disabled={acting[a.id]}
                          className="inline-flex items-center gap-1.5 rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-1.5 text-xs font-medium text-rose-300 transition-colors hover:bg-rose-500/20 disabled:opacity-50"
                        >
                          <X className="h-3.5 w-3.5" />
                          Reject
                        </button>
                      </div>
                    </>
                  ) : (
                    <span className="text-xs text-ink-500">
                      {a.status === "expired" ? "timed out" : "decided"}
                    </span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
