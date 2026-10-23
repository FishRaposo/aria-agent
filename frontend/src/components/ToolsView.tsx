"use client";

import { ChevronDown, RefreshCw, ShieldCheck, Wrench } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import clsx from "clsx";
import { PermissionBadge } from "@/components/Badges";
import PageHeader from "@/components/PageHeader";
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/States";
import { api, ApiError } from "@/lib/api";
import { useDemoRevision } from "@/lib/use-demo";
import { getProviderMode } from "@/lib/demo-scenarios";
import type { JsonSchemaProperty, ToolSpec } from "@/types";

function SchemaTable({ tool }: { tool: ToolSpec }) {
  const props = tool.schema?.properties ?? {};
  const required = new Set(tool.schema?.required ?? []);
  const entries = Object.entries(props) as [string, JsonSchemaProperty][];
  if (entries.length === 0) {
    return <p className="text-xs text-ink-400">No parameters.</p>;
  }
  return (
    <table className="w-full text-left text-xs">
      <thead className="text-ink-400">
        <tr className="border-b border-ink-800">
          <th className="py-1.5 pr-3 font-medium">Parameter</th>
          <th className="py-1.5 pr-3 font-medium">Type</th>
          <th className="py-1.5 font-medium">Description</th>
        </tr>
      </thead>
      <tbody className="text-ink-300">
        {entries.map(([name, prop]) => (
          <tr key={name} className="border-b border-ink-900 last:border-0">
            <td className="py-1.5 pr-3">
              <span className="mono text-ink-100">{name}</span>
              {required.has(name) && (
                <span className="ml-1 text-rose-400" title="required">
                  *
                </span>
              )}
            </td>
            <td className="py-1.5 pr-3 mono text-ink-400">
              {prop.type ?? "—"}
            </td>
            <td className="py-1.5 text-ink-400">{prop.description ?? "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ToolCard({ tool }: { tool: ToolSpec }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="card">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div
            className={clsx(
              "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg",
              tool.permission === "safe"
                ? "bg-emerald-500/15 text-emerald-300"
                : "bg-amber-500/15 text-amber-300"
            )}
          >
            {tool.permission === "safe" ? (
              <Wrench className="h-4 w-4" />
            ) : (
              <ShieldCheck className="h-4 w-4" />
            )}
          </div>
          <div>
            <h3 className="mono font-semibold text-ink-100">{tool.name}</h3>
            <p className="mt-0.5 max-w-xl text-sm text-ink-400">
              {tool.description}
            </p>
          </div>
        </div>
        <PermissionBadge permission={tool.permission} />
      </div>

      <button
        onClick={() => setOpen((v) => !v)}
        className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-brand-300 hover:text-brand-200"
      >
        <ChevronDown
          className={clsx("h-3.5 w-3.5 transition-transform", open && "rotate-180")}
        />
        {open ? "Hide schema" : "Show schema"}
      </button>

      {open && (
        <div className="mt-3 rounded-lg border border-ink-800 bg-ink-950/50 p-3">
          <SchemaTable tool={tool} />
        </div>
      )}
    </div>
  );
}

export default function ToolsView() {
  const [tools, setTools] = useState<ToolSpec[]>([]);
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
      const res = await api.listTools();
      if (requestId !== requestSequence.current) return;
      setTools(res.data);
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
          : "Failed to load tools"
      );
    } finally {
      if (requestId === requestSequence.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    return () => { requestSequence.current += 1; };
  }, [load, revision]);

  const safe = tools.filter((t) => t.permission === "safe").length;
  const gated = tools.length - safe;

  return (
    <div>
      <PageHeader
        title="Tool registry"
        description="Tools the agent can call, with JSON schemas and permission levels. Risky tools route through the approval queue in approval-gated mode."
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
        <LoadingSkeleton rows={4} />
      ) : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : tools.length === 0 ? (
        <EmptyState
          title="No tools registered"
          message="The registry returned no tools."
          icon={<Wrench className="h-9 w-9" />}
        />
      ) : (
        <div className="space-y-5">
          <div className="flex flex-wrap gap-3 text-sm text-ink-400">
            <span className="rounded-lg border border-ink-800 bg-ink-900/60 px-3 py-1.5">
              {tools.length} tools
            </span>
            <span className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-3 py-1.5 text-emerald-300">
              {safe} safe
            </span>
            <span className="rounded-lg border border-amber-500/20 bg-amber-500/5 px-3 py-1.5 text-amber-300">
              {gated} require approval
            </span>
          </div>
          {demo && <div className="card border-rose-400/25"><p className="eyebrow text-rose-300">NOT AVAILABLE</p><h2 className="mono mt-2 font-semibold text-ink-100">email_send</h2><p className="mt-2 text-sm text-ink-300">Not in the permitted registry. Repository text cannot add it. The unauthorized story is denied at this boundary.</p></div>}
          <p className="text-xs text-ink-300">Safe tools can run after schema validation. Write tools require review. Unregistered actions are not available.</p>
          <div className="grid gap-4" data-testid="tool-list">
            {tools.map((tool) => (
              <ToolCard key={tool.name} tool={tool} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
