import {
  Activity,
  CheckSquare,
  Database,
  GitBranch,
  MessageSquare,
  ShieldCheck,
  Wrench,
} from "lucide-react";
import Link from "next/link";

const FEATURES = [
  {
    href: "/runs",
    icon: Activity,
    title: "Run history & traces",
    body: "Every agent run with a span-level trace timeline — routing decisions, tool calls, durations, and status.",
  },
  {
    href: "/chat",
    icon: MessageSquare,
    title: "Chat with the agent",
    body: "Drive the reason-and-act loop live. Watch tool calls, approvals, and per-message cost as they happen.",
  },
  {
    href: "/tools",
    icon: Wrench,
    title: "Tool registry",
    body: "Inspect registered tools, their JSON schemas, and permission levels — safe vs. requires-approval.",
  },
  {
    href: "/approvals",
    icon: CheckSquare,
    title: "Approval queue",
    body: "Govern risky write actions. Approve or reject pending tool calls before they execute.",
  },
  {
    href: "/memory",
    icon: Database,
    title: "Memory inspector",
    body: "Browse the conversation memory the agent carries across turns within a session.",
  },
  {
    href: "/runs",
    icon: GitBranch,
    title: "Cost & latency charts",
    body: "Per-run cost and latency, visualised — spot the expensive and the slow at a glance.",
  },
];

export default function HomePage() {
  return (
    <div className="space-y-12">
      <section className="rounded-2xl border border-ink-800 bg-gradient-to-br from-ink-900 via-ink-900 to-brand-950/40 px-8 py-14 text-center">
        <span className="mb-4 inline-flex items-center gap-2 rounded-full border border-brand-500/30 bg-brand-500/10 px-3 py-1 text-xs font-medium text-brand-200">
          <ShieldCheck className="h-3.5 w-3.5" />
          Offline-first agent control plane
        </span>
        <h1 className="mx-auto mb-4 max-w-3xl text-4xl font-bold tracking-tight text-ink-50 sm:text-5xl">
          The ARIA Agent Control Console
        </h1>
        <p className="mx-auto mb-8 max-w-2xl text-lg text-ink-400">
          Operate an autonomous agent with full observability: trace every run,
          govern risky tool calls behind an approval gate, and track cost and
          latency on every step.
        </p>
        <div className="flex flex-wrap justify-center gap-3">
          <Link href="/runs" className="btn-primary">
            <Activity className="h-4 w-4" />
            View runs
          </Link>
          <Link href="/chat" className="btn-secondary">
            <MessageSquare className="h-4 w-4" />
            Chat with the agent
          </Link>
        </div>
      </section>

      <section className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
        {FEATURES.map(({ href, icon: Icon, title, body }) => (
          <Link
            key={title}
            href={href}
            className="group rounded-xl border border-ink-800 bg-ink-900/60 p-6 transition-colors hover:border-brand-500/40 hover:bg-ink-900"
          >
            <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-brand-600/15 text-brand-300 transition-colors group-hover:bg-brand-600/25">
              <Icon className="h-5 w-5" />
            </div>
            <h3 className="mb-1.5 font-semibold text-ink-100">{title}</h3>
            <p className="text-sm text-ink-400">{body}</p>
          </Link>
        ))}
      </section>
    </div>
  );
}
