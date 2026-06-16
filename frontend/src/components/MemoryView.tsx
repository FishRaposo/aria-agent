"use client";

import { Bot, Database, RefreshCw, User } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import clsx from "clsx";
import PageHeader from "@/components/PageHeader";
import { EmptyState, ErrorState, LoadingSkeleton } from "@/components/States";
import { api, ApiError } from "@/lib/api";
import type { MemoryMessage } from "@/types";

export default function MemoryView() {
  const [messages, setMessages] = useState<MemoryMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [demo, setDemo] = useState(false);
  const [demoReason, setDemoReason] = useState<string | undefined>();
  const [session, setSession] = useState("default");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getMemory(session);
      setMessages(res.data);
      setDemo(res.demo);
      setDemoReason(res.demoReason);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? `${err.message} (HTTP ${err.status})`
          : err instanceof Error
          ? err.message
          : "Failed to load memory"
      );
    } finally {
      setLoading(false);
    }
  }, [session]);

  useEffect(() => {
    load();
  }, [load]);

  const userCount = messages.filter((m) => m.role === "user").length;

  return (
    <div>
      <PageHeader
        title="Memory inspector"
        description="The conversation memory the agent carries across turns within a session. Built from persisted run history."
        demo={demo}
        demoReason={demoReason}
        actions={
          <div className="flex items-center gap-2">
            <label className="flex items-center gap-2 text-sm text-ink-400">
              Session
              <input
                value={session}
                onChange={(e) => setSession(e.target.value)}
                className="w-32 rounded-lg border border-ink-700 bg-ink-900 px-3 py-1.5 text-sm text-ink-100 outline-none focus:border-brand-500"
              />
            </label>
            <button onClick={load} className="btn-secondary" disabled={loading}>
              <RefreshCw className={loading ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
              Refresh
            </button>
          </div>
        }
      />

      {loading ? (
        <LoadingSkeleton rows={4} />
      ) : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : messages.length === 0 ? (
        <EmptyState
          title="No memory for this session"
          message="Run a few turns in the Chat view, then inspect the resulting memory here."
          icon={<Database className="h-9 w-9" />}
        />
      ) : (
        <div className="space-y-4">
          <div className="flex flex-wrap gap-3 text-sm text-ink-400">
            <span className="rounded-lg border border-ink-800 bg-ink-900/60 px-3 py-1.5">
              {messages.length} messages
            </span>
            <span className="rounded-lg border border-ink-800 bg-ink-900/60 px-3 py-1.5">
              {userCount} turns
            </span>
            <span className="mono rounded-lg border border-ink-800 bg-ink-900/60 px-3 py-1.5 text-ink-300">
              session: {session}
            </span>
          </div>

          <div className="card space-y-3" data-testid="memory-list">
            {messages.map((m, i) => {
              const isUser = m.role === "user";
              return (
                <div
                  key={i}
                  className={clsx(
                    "flex items-start gap-3",
                    isUser ? "" : "flex-row-reverse text-right"
                  )}
                >
                  <span
                    className={clsx(
                      "mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full",
                      isUser
                        ? "bg-ink-800 text-ink-300"
                        : "bg-brand-600/20 text-brand-300"
                    )}
                  >
                    {isUser ? (
                      <User className="h-4 w-4" />
                    ) : (
                      <Bot className="h-4 w-4" />
                    )}
                  </span>
                  <div className="min-w-0">
                    <div className="mb-0.5 text-[11px] uppercase tracking-wide text-ink-600">
                      {m.role}
                    </div>
                    <div
                      className={clsx(
                        "inline-block max-w-2xl rounded-xl px-3 py-2 text-sm",
                        isUser
                          ? "bg-ink-800/60 text-ink-100"
                          : "bg-brand-600/10 text-ink-100"
                      )}
                    >
                      {m.content}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
