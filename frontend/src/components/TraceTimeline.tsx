"use client";

import clsx from "clsx";
import {
  Brain,
  GitBranch,
  ShieldAlert,
  Wrench,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import { useState } from "react";
import type { Span, TraceSummary } from "@/types";
import { formatMs } from "@/lib/format";

interface TraceTimelineProps {
  trace: TraceSummary;
}

const TYPE_META: Record<
  string,
  { icon: typeof Brain; tint: string; label: string }
> = {
  other: { icon: GitBranch, tint: "text-ink-300", label: "run" },
  decision: { icon: GitBranch, tint: "text-brand-300", label: "decision" },
  tool: { icon: Wrench, tint: "text-emerald-300", label: "tool" },
  llm: { icon: Brain, tint: "text-violet-300", label: "llm" },
  retrieval: { icon: Brain, tint: "text-sky-300", label: "retrieval" },
};

function iconFor(span: Span) {
  if (span.name.startsWith("approval"))
    return { icon: ShieldAlert, tint: "text-amber-300", label: "approval" };
  return TYPE_META[span.span_type] ?? TYPE_META.other;
}

export default function TraceTimeline({ trace }: TraceTimelineProps) {
  // The root "agent.run" span wraps the whole run; skip it in the per-step
  // list and use it for scaling. Identify it by name (falling back to the
  // first span) rather than parent linkage, which may be absent.
  const rootIndex = Math.max(
    0,
    trace.spans.findIndex((s) => s.name === "agent.run")
  );
  const root = trace.spans[rootIndex];
  const steps = trace.spans.filter((_, i) => i !== rootIndex);
  const totalMs = trace.duration_ms || root?.end_ms || 1;

  if (steps.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-ink-700 bg-ink-900/40 px-4 py-6 text-center text-sm text-ink-500">
        No spans recorded for this run.
      </p>
    );
  }

  return (
    <ol className="space-y-2" data-testid="trace-timeline">
      {steps.map((span, idx) => (
        <SpanRow key={span.span_id} span={span} index={idx + 1} totalMs={totalMs} />
      ))}
    </ol>
  );
}

function SpanRow({
  span,
  index,
  totalMs,
}: {
  span: Span;
  index: number;
  totalMs: number;
}) {
  const [open, setOpen] = useState(false);
  const meta = iconFor(span);
  const Icon = meta.icon;
  const duration =
    span.end_ms !== null ? Math.max(0, span.end_ms - span.start_ms) : null;
  const widthPct =
    duration && totalMs > 0
      ? Math.min(100, Math.max(2, (duration / totalMs) * 100))
      : 2;
  const offsetPct =
    totalMs > 0 ? Math.min(98, (span.start_ms / totalMs) * 100) : 0;
  const isError = span.status === "error";
  const hasDetail =
    span.attributes && Object.keys(span.attributes).length > 0;

  return (
    <li className="rounded-lg border border-ink-800 bg-ink-900/50">
      <button
        type="button"
        onClick={() => hasDetail && setOpen((v) => !v)}
        className={clsx(
          "flex w-full items-center gap-3 px-4 py-3 text-left",
          hasDetail && "cursor-pointer hover:bg-ink-800/40"
        )}
      >
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-ink-800 text-xs font-semibold text-ink-400">
          {index}
        </span>
        <Icon className={clsx("h-4 w-4 shrink-0", meta.tint)} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="mono truncate text-ink-100">{span.name}</span>
            {isError ? (
              <XCircle className="h-3.5 w-3.5 shrink-0 text-rose-400" />
            ) : (
              <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-400" />
            )}
          </div>
          {/* Mini gantt bar */}
          <div className="mt-1.5 h-1.5 w-full rounded-full bg-ink-800">
            <div
              className={clsx(
                "h-1.5 rounded-full",
                isError ? "bg-rose-500/70" : "bg-brand-500/70"
              )}
              style={{ width: `${widthPct}%`, marginLeft: `${offsetPct}%` }}
            />
          </div>
        </div>
        <span className="mono shrink-0 text-xs text-ink-400">
          {formatMs(duration)}
        </span>
      </button>

      {open && hasDetail && (
        <pre className="overflow-x-auto border-t border-ink-800 bg-ink-950/60 px-4 py-3 text-xs text-ink-300">
          {JSON.stringify(span.attributes, null, 2)}
        </pre>
      )}
    </li>
  );
}
