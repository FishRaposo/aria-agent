import { AlertCircle, Inbox, RefreshCw } from "lucide-react";
import type { ReactNode } from "react";

/** Skeleton placeholder rows for loading data views. */
export function LoadingSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div data-testid="loading-skeleton" className="space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="animate-pulse rounded-xl border border-ink-800 bg-ink-900/60 p-5"
        >
          <div className="mb-3 h-4 w-1/3 rounded bg-ink-800" />
          <div className="mb-2 h-3 w-2/3 rounded bg-ink-800/70" />
          <div className="h-3 w-1/2 rounded bg-ink-800/70" />
        </div>
      ))}
    </div>
  );
}

export function EmptyState({
  title,
  message,
  icon,
}: {
  title: string;
  message: string;
  icon?: ReactNode;
}) {
  return (
    <div
      data-testid="empty-state"
      className="flex flex-col items-center justify-center rounded-xl border border-dashed border-ink-700 bg-ink-900/40 px-6 py-14 text-center"
    >
      <div className="mb-3 text-ink-500">{icon ?? <Inbox className="h-9 w-9" />}</div>
      <h3 className="mb-1 text-sm font-semibold text-ink-200">{title}</h3>
      <p className="max-w-sm text-sm text-ink-400">{message}</p>
    </div>
  );
}

export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div
      data-testid="error-state"
      className="flex flex-col items-center justify-center rounded-xl border border-rose-500/30 bg-rose-500/5 px-6 py-12 text-center"
    >
      <AlertCircle className="mb-3 h-9 w-9 text-rose-400" />
      <h3 className="mb-1 text-sm font-semibold text-rose-200">
        Could not load data
      </h3>
      <p className="mb-4 max-w-md text-sm text-rose-300/80">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="inline-flex items-center gap-2 rounded-lg bg-rose-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-rose-700"
        >
          <RefreshCw className="h-4 w-4" />
          Retry
        </button>
      )}
    </div>
  );
}
