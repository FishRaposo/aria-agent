"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ArrowRight, Database, RotateCcw, ShieldCheck, X } from "lucide-react";
import { getProviderMode, getResetKey, getGuidedStep, setGuidedStep, resetDemo, setProviderMode, tickDemo, SAFE_RUN, DRAFT_RUN, DENIED_RUN } from "@/lib/demo-scenarios";
import { useDemoRevision } from "@/lib/use-demo";
const STEPS = [
  { title: "A safe action can run", body: "Inspect the validated expression, permission decision, and result. Every decision has a place in the timeline.", href: `/runs/${SAFE_RUN}`, next: `/runs/${DRAFT_RUN}` },
  { title: "You control the write boundary", body: "Review the exact draft. Reject it to see Not executed, then reset the scenario and approve it once. Nothing is sent.", href: `/runs/${DRAFT_RUN}`, next: `/runs/${DENIED_RUN}` },
  { title: "Repository text cannot grant permission", body: "An untrusted instruction proposes email_send. The tool boundary denies it before execution.", href: `/runs/${DENIED_RUN}`, next: "/skills" },
  { title: "Instructions and permissions are separate", body: "The calculator skill loaded for a matching request. Loading a skill never grants a tool permission.", href: "/skills", next: "/setup" },
  { title: "From preview to reproducible proof", body: "The sample illustrates the design. The setup case identifies tested contracts and the native runtime evidence still required.", href: "/setup", next: "/runs" },
];
export default function DemoShell({ children }: { children: React.ReactNode }) {
  useDemoRevision();
  const pathname = usePathname();
  const mode = getProviderMode(); const step = getGuidedStep();
  const resetVersion = getResetKey();
  const [notice, setNotice] = useState("");
  const [paused, setPaused] = useState(false);
  const resetRef = useRef<HTMLButtonElement>(null);
  useEffect(() => { setPaused(false); }, [resetVersion]);
  useEffect(() => { const timer = setInterval(() => tickDemo(), 1000); return () => clearInterval(timer); }, []);
  useEffect(() => { setNotice(""); }, [pathname]);
  return <>
    <div className="demo-toolbar">
      <div className="demo-toolbar-inner">
        <span className="inline-flex items-center gap-2 text-xs font-medium text-ink-200" data-testid="provider-label">
          {mode === "sample" ? <Database className="h-3.5 w-3.5 text-brand-300" /> : <ShieldCheck className="h-3.5 w-3.5 text-emerald-300" />}
          {mode === "sample" ? "Interactive sample data" : "Connected API mode"}
          <span className="hidden font-normal text-ink-400 md:inline">{mode === "sample" ? "Tab-local simulation · no backend calls" : "Transport errors are shown explicitly"}</span>
        </span>
        <div className="flex items-center gap-3">
          <button className="text-xs text-ink-300 hover:text-white" onClick={() => { setProviderMode(mode === "sample" ? "connected" : "sample"); setNotice(mode === "sample" ? "Connected API selected." : "Sample demo selected."); }}>{mode === "sample" ? "Connect API" : "Enter sample demo"}</button>
          {mode === "sample" && <button ref={resetRef} className="inline-flex items-center gap-1.5 text-xs font-medium text-brand-200" onClick={() => { resetDemo(); setNotice("Demo reset. All scenarios restored."); requestAnimationFrame(() => resetRef.current?.focus()); }}><RotateCcw className="h-3.5 w-3.5" />Reset demo</button>}
        </div>
      </div>
    </div>
    <p role="status" className="sr-only">{notice}</p>
    {step >= 0 && mode === "sample" && <aside aria-label="Guided demo" className="tour-bar mx-auto mt-6 max-w-7xl rounded-xl border border-brand-400/30 bg-brand-500/10 p-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 flex-1"><p className="eyebrow text-brand-300">Guided demo · {step + 1} / {STEPS.length} {paused && "· paused"}</p><h2 className="mt-1 font-semibold text-ink-50">{STEPS[step].title}</h2><p className="mt-1 max-w-3xl text-sm text-ink-300">{STEPS[step].body}</p></div>
        <div className="flex flex-wrap items-center gap-3">
          <button className="text-xs text-ink-300" onClick={() => setPaused(!paused)}>{paused ? "Resume tour" : "Pause tour"}</button>
          {!paused && <Link href={STEPS[step].next} className="btn-secondary" onClick={() => setGuidedStep(step === 4 ? -1 : step + 1)}>{step === 4 ? "Finish tour" : "Next step"}<ArrowRight className="h-4 w-4" /></Link>}
          <button aria-label="Exit guided demo" onClick={() => setGuidedStep(-1)} className="rounded-lg p-2 text-ink-300"><X className="h-4 w-4" /></button>
        </div>
      </div>
      <div className="mt-3 flex gap-1" aria-hidden="true">{STEPS.map((_, i) => <span key={i} className={`h-1 flex-1 rounded-full ${i <= step ? "bg-brand-400" : "bg-ink-700"}`} />)}</div>
    </aside>}
    <div key={`${mode}-${getResetKey()}`}>{children}</div>
  </>;
}
