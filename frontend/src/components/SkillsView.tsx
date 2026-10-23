"use client";

import {
  BookOpen,
  ChevronDown,
  EyeOff,
  Lock,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import clsx from "clsx";
import PageHeader from "@/components/PageHeader";
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/States";
import { api, ApiError } from "@/lib/api";
import { useDemoRevision } from "@/lib/use-demo";
import { getProviderMode, getSessionId } from "@/lib/demo-scenarios";
import type { ActivatedSkill, AgentRun, SkillCatalogEntry, SkillsSnapshot } from "@/types";

function ScopeBadge({ scope }: { scope: string }) {
  return (
    <span className="inline-flex items-center rounded-full border border-ink-700 bg-ink-800/60 px-2 py-0.5 text-[11px] font-medium capitalize text-ink-400">
      {scope}
    </span>
  );
}

function ActivatedCard({ skill, sample }: { skill: ActivatedSkill; sample: boolean }) {
  const [open, setOpen] = useState(true);
  return (
    <div className="card border-brand-500/25 bg-brand-500/5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="mb-1 flex flex-wrap items-center gap-2">
            <Sparkles className="h-4 w-4 text-brand-300" />
            <h3 className="mono font-semibold text-ink-50">{skill.name}</h3>
            <ScopeBadge scope={skill.scope} />
            <span className="rounded-full border border-emerald-400/30 bg-emerald-400/10 px-2 py-0.5 text-[11px] font-medium text-emerald-300">
              Activated
            </span>
          </div>
          <p className="mb-2 max-w-xl text-xs text-ink-300">Why loaded: {skill.selection_reason || (sample ? "The recorded sample explicitly activated these instructions." : "The recorded selection reason is unavailable.")} Loading a skill does not grant tool permission.</p>
          <p className="text-xs text-ink-400">{skill.selection_method || (sample ? "explicit" : "unknown")} selection · recorded source: {skill.source}</p>
          {skill.content_hash && <p className="mono mt-2 break-all text-xs text-ink-400">{skill.content_hash}</p>}
          {skill.activation_command && (
            <p className="mono text-xs text-brand-200">{skill.activation_command}</p>
          )}
          <Link
            href={`/runs/${skill.run_id}`}
            className="mt-1 inline-block text-xs text-brand-300 hover:underline"
          >
            from run {skill.run_id}
          </Link>
        </div>
        <button
          onClick={() => setOpen((v) => !v)}
          className="inline-flex items-center gap-1 text-xs font-medium text-brand-300 hover:text-brand-200"
        >
          <ChevronDown
            className={clsx("h-3.5 w-3.5 transition-transform", open && "rotate-180")}
          />
          {open ? "Hide instructions" : "Show instructions"}
        </button>
      </div>
      {open && (
        <pre className="mono mt-3 max-h-64 overflow-auto rounded-lg border border-ink-800 bg-ink-950/70 p-3 text-xs leading-relaxed text-ink-200">
          {skill.instructions}
        </pre>
      )}
    </div>
  );
}

function InactiveCard({ skill }: { skill: SkillCatalogEntry }) {
  const [hintsOpen, setHintsOpen] = useState(false);
  return (
    <div className="card opacity-90">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="mb-1 flex flex-wrap items-center gap-2">
            <Lock className="h-4 w-4 text-ink-500" />
            <h3 className="mono font-semibold text-ink-200">{skill.name}</h3>
            <ScopeBadge scope={skill.scope} />
            <span className="inline-flex items-center gap-1 rounded-full border border-ink-700 bg-ink-900/60 px-2 py-0.5 text-[11px] font-medium text-ink-500">
              <EyeOff className="h-3 w-3" />
              Instructions withheld
            </span>
          </div>
          <p className="max-w-2xl text-sm text-ink-400">{skill.description}</p>
          <p className="mono mt-1 text-xs text-ink-600">{skill.source}</p>
        </div>
        {skill.activation_hints && (
          <button
            onClick={() => setHintsOpen((v) => !v)}
            className="inline-flex items-center gap-1 text-xs font-medium text-ink-400 hover:text-ink-200"
          >
            <ChevronDown
              className={clsx(
                "h-3.5 w-3.5 transition-transform",
                hintsOpen && "rotate-180"
              )}
            />
            {hintsOpen ? "Hide hints" : "Show activation hints"}
          </button>
        )}
      </div>
      {hintsOpen && skill.activation_hints && (
        <pre className="mono mt-3 rounded-lg border border-dashed border-ink-700 bg-ink-950/40 p-3 text-xs text-ink-400">
          {skill.activation_hints}
        </pre>
      )}
      {!skill.activation_hints && (
        <p className="mt-3 text-xs text-ink-600">
          Metadata only — instructions load only when a request selects this skill.
        </p>
      )}
    </div>
  );
}

export default function SkillsView() {
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [selectedRun, setSelectedRun] = useState("");
  const sequence = useRef(0);
  useEffect(() => { if (getProviderMode() === "connected") setSelectedRun(new URLSearchParams(window.location.search).get("run_id") || ""); }, []);
  const [snapshot, setSnapshot] = useState<SkillsSnapshot | null>(null);
  const revision = useDemoRevision();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [demo, setDemo] = useState(false);
  const [demoForced, setDemoForced] = useState(false);
  const [demoReason, setDemoReason] = useState<string | undefined>();

  const load = useCallback(async () => {
    const requestId = ++sequence.current;
    if (getProviderMode() !== "sample") setLoading(true);
    setError(null);
    try {
      const [res, history] = await Promise.all([api.getSkills(getSessionId(), selectedRun || undefined), api.listRuns(50, getSessionId())]);
      if (requestId !== sequence.current) return;
      setRuns(history.data);
      setSnapshot(res.data);
      setDemo(res.demo);
      setDemoForced(Boolean(res.demoForced));
      setDemoReason(res.demoReason);
    } catch (err) {
      if (requestId !== sequence.current) return;
      setError(
        err instanceof ApiError
          ? `${err.message} (HTTP ${err.status})`
          : err instanceof Error
          ? err.message
          : "Failed to load skills"
      );
    } finally {
      if (requestId === sequence.current) setLoading(false);
    }
  }, [selectedRun]);

  useEffect(() => {
    load();
    return () => { sequence.current += 1; };
  }, [load, revision]);

  const activatedNames = useMemo(
    () => new Set(snapshot?.activated.map((s) => s.name) ?? []),
    [snapshot]
  );

  const inactive = useMemo(
    () =>
      snapshot?.catalog.filter((entry) => !activatedNames.has(entry.name)) ?? [],
    [snapshot, activatedNames]
  );

  return (
    <div>
      <PageHeader
        title="Agent skills"
        description="Inspect the instructions recorded for one saved run. Automatic matching selects relevant skills; loaded instructions never grant tool permissions."
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

      {!demo && <div className="card mb-6"><label className="block text-xs text-ink-400">Skill evidence run<select aria-label="Skill evidence run" value={selectedRun} onChange={event => setSelectedRun(event.target.value)} className="mt-2 w-full rounded-lg border border-ink-700 bg-ink-950 p-3 text-sm text-ink-100"><option value="">Latest run in session {getSessionId()}</option>{runs.map(run => <option key={run.id} value={run.id}>{run.id} — {run.query}</option>)}</select></label><p className="mt-3 text-xs text-ink-400">Current catalog metadata is separate from immutable instructions recorded when the selected run started.</p></div>}
      {snapshot && (
        <div className="mb-6 grid gap-3 sm:grid-cols-3">
          <div className="stat-card">
            <p className="text-xs text-ink-500">Visible in catalog</p>
            <p className="mt-1 text-2xl font-semibold text-ink-50">
              {snapshot.context_report.visible_skill_count}
            </p>
          </div>
          <div className="stat-card">
            <p className="text-xs text-ink-500">Loaded for selected run</p>
            <p className="mt-1 text-2xl font-semibold text-brand-200">
              {snapshot.activated.length}
            </p>
          </div>
          <div className="stat-card">
            <p className="text-xs text-ink-500">Instructions withheld</p>
            <p className="mt-1 text-2xl font-semibold text-ink-300">
              {inactive.length}
            </p>
          </div>
        </div>
      )}

      {loading ? (
        <LoadingSkeleton rows={4} />
      ) : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : !snapshot ? (
        <EmptyState
          title="No skills discovered"
          message="The registry returned an empty skill snapshot."
          icon={<BookOpen className="h-9 w-9" />}
        />
      ) : (
        <div className="space-y-8" data-testid="skills-view">
          {snapshot.context_available === false && <div className="card border-amber-400/30"><h2 className="font-semibold text-amber-200">No recorded skill evidence</h2><p className="mt-2 text-sm text-ink-300">{snapshot.run_id ? "This historical run predates durable skill evidence. Its instructions and activation state are unknown." : "No run has recorded skill context in this session yet. Start a connected request to inspect its selection."}</p></div>}
          {snapshot.context_available !== false && <div className="card"><p className="text-sm text-ink-200">{snapshot.run_id ? `Recorded run: ${snapshot.run_id}` : "Sample skill context"}</p><p className="mt-2 text-xs text-ink-300">{demo ? "Illustrative instructions in sample data." : snapshot.activated.length === 0 ? "No instruction bodies loaded. No model consumption recorded." : snapshot.context_report.context_consumed ? "Instructions were passed to a model context; this does not establish their effectiveness." : "Loaded into prepared context; not consumed by a model. Keyword execution makes no model-use claim."}</p></div>}
          <section>
            <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-brand-200">
              <Sparkles className="h-4 w-4" />
              Activated — instructions loaded
            </h2>
            <div className="space-y-3">
              {snapshot.context_available !== false && snapshot.activated.length === 0 && <p className="text-sm text-ink-400">No skill matched this request. No instruction bodies loaded.</p>}
              {snapshot.activated.map((skill) => (
                <ActivatedCard key={skill.name} skill={skill} sample={demo} />
              ))}
            </div>
          </section>

          <section>
            <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-ink-400">
              <Lock className="h-4 w-4" />
              Closed — metadata only
            </h2>
            <div className="space-y-3">
              {inactive.map((skill) => (
                <InactiveCard key={skill.name} skill={skill} />
              ))}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
