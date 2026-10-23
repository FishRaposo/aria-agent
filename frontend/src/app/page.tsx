"use client";
import ConnectedWorkspace from "@/components/ConnectedWorkspace";
import { useDemoRevision } from "@/lib/use-demo";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowDown, ArrowRight, Check, ChevronRight, Fingerprint, LockKeyhole, Play, ShieldCheck, Terminal } from "lucide-react";
import { getProviderMode, setProviderMode, setGuidedStep, SAFE_RUN, DRAFT_RUN, DENIED_RUN } from "@/lib/demo-scenarios";
const STORIES = [
  { number: "01", title: "Safe by design", subtitle: "Validate. Permit. Calculate.", label: "Completed", href: `/runs/${SAFE_RUN}`, color: "safe", icon: Check },
  { number: "02", title: "Your decision matters", subtitle: "A draft waits for your review.", label: "Needs approval", href: `/runs/${DRAFT_RUN}`, color: "review", icon: Fingerprint },
  { number: "03", title: "A boundary that holds", subtitle: "Untrusted instructions are denied.", label: "Not executed", href: `/runs/${DENIED_RUN}`, color: "denied", icon: LockKeyhole },
];
export default function HomePage() {
  useDemoRevision();
  const router = useRouter();
  const openSample = (event: React.MouseEvent<HTMLAnchorElement>, href: string, guided = false) => { event.preventDefault(); setProviderMode("sample"); if (guided) setGuidedStep(0); router.push(href); };
  return <div className="landing">
    {getProviderMode() === "connected" && <ConnectedWorkspace />}
    <section className="hero-grid">
      <div className="hero-copy">
        <p className="eyebrow flex items-center gap-2 text-brand-300"><span className="h-1.5 w-1.5 rounded-full bg-brand-300" />ARIA / CONTROLLED AGENT EXECUTION</p>
        <h1>An agent you can<br /><span>inspect and control.</span></h1>
        <p className="hero-description">Useful autonomy needs a boundary.<br className="hidden sm:block" /> Trace the request. Review the action.<br className="hidden sm:block" /> Know exactly what happened.</p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link href={`/runs/${SAFE_RUN}`} className="btn-primary hero-cta" onClick={event => openSample(event, `/runs/${SAFE_RUN}`, true)}><Play className="h-4 w-4" fill="currentColor" />Start guided demo<ArrowRight className="h-4 w-4" /></Link>
          <Link href="/runs" className="btn-secondary hero-cta" onClick={event => openSample(event, "/runs")}>Explore freely</Link>
        </div>
        <p className="mt-4 text-xs text-ink-400">3 minutes · interactive fixtures · no credentials needed</p>
        <div className="mt-5 flex flex-wrap gap-4 text-xs text-brand-200"><Link href="/setup#actual-project">Run the actual project →</Link><Link href="/setup#engineering-evidence">View engineering evidence →</Link></div>
        <div className="hero-principles"><span><ShieldCheck />Permissioned tools</span><span><Fingerprint />Human review</span><span><Terminal />Inspectable trace</span></div>
      </div>
      <div className="control-artifact" aria-label="Example of an inspectable approval boundary">
        <div className="artifact-top"><span className="inline-flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-brand-400" /> EXECUTION RECORD</span><span className="mono text-ink-400">run / c9d0e1f2</span></div>
        <div className="artifact-request"><span className="eyebrow text-ink-400">01 / REQUEST</span><p>“Draft the incident follow-up.”</p><span className="mono text-xs text-ink-400">source: user · authority: request</span></div>
        <div className="artifact-line"><ArrowDown className="h-4 w-4" /></div>
        <div className="artifact-tool"><div className="flex items-center justify-between gap-2"><span className="mono text-brand-200">email_draft</span><span className="text-xs text-emerald-300">✓ Schema valid</span></div><p className="mono mt-3 text-xs text-ink-400">recipient: ops@example.test<br />subject: Incident follow-up</p></div>
        <div className="artifact-boundary"><div className="artifact-boundary-label"><Fingerprint className="h-4 w-4" />HUMAN APPROVAL BOUNDARY</div><div className="flex items-center justify-between gap-3"><p className="text-sm font-medium text-amber-100">Execution paused.</p><span className="text-xs text-amber-200/80">You decide what runs.</span></div></div>
        <div className="artifact-footer"><LockKeyhole className="h-4 w-4" /><span>No approval. No execution.</span><span className="ml-auto text-ink-400">SIMULATION</span></div>
      </div>
    </section>
    <section className="stories-section" aria-label="Three execution stories"><div className="mb-5 flex flex-wrap items-end justify-between gap-2"><div><p className="eyebrow text-ink-400">THREE REQUESTS. THREE OUTCOMES.</p><h2 className="mt-2 text-xl font-semibold text-ink-100">Follow the decision, not just the answer.</h2></div><Link href="/setup" className="inline-flex items-center gap-1 text-xs text-brand-200">See the real setup case<ArrowRight className="h-3.5 w-3.5" /></Link></div>
      <div className="story-grid">{STORIES.map(({ number, title, subtitle, label, href, color, icon: Icon }) => <Link href={href} key={number} className={`story-card ${color}`} onClick={event => openSample(event, href)}><div className="flex items-center justify-between"><span className="mono text-xs text-ink-400">{number}</span><span className="story-status"><Icon className="h-3 w-3" />{label}</span></div><h3>{title}</h3><p>{subtitle}</p><div className="story-card-bottom"><span>Inspect story</span><ChevronRight className="h-4 w-4" /></div></Link>)}</div>
    </section>
    <footer className="landing-footer"><span>Instructions ≠ permissions ≠ verified outcomes.</span><span>Offline-first · Python / FastAPI / Next.js</span></footer>
  </div>;
}
