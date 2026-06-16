import clsx from "clsx";
import type { RunStatus } from "@/types";

const RUN_STATUS_STYLES: Record<RunStatus, string> = {
  completed: "border-emerald-400/30 bg-emerald-400/10 text-emerald-300",
  pending_approval: "border-amber-400/30 bg-amber-400/10 text-amber-300",
  blocked: "border-orange-400/30 bg-orange-400/10 text-orange-300",
  error: "border-rose-400/30 bg-rose-400/10 text-rose-300",
};

const RUN_STATUS_LABELS: Record<RunStatus, string> = {
  completed: "Completed",
  pending_approval: "Pending approval",
  blocked: "Blocked",
  error: "Error",
};

export function StatusBadge({ status }: { status: RunStatus }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium",
        RUN_STATUS_STYLES[status] ??
          "border-ink-600 bg-ink-700/40 text-ink-300"
      )}
    >
      {RUN_STATUS_LABELS[status] ?? status}
    </span>
  );
}

export function PermissionBadge({
  permission,
}: {
  permission: "safe" | "requires_approval";
}) {
  const safe = permission === "safe";
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium",
        safe
          ? "border-emerald-400/30 bg-emerald-400/10 text-emerald-300"
          : "border-amber-400/30 bg-amber-400/10 text-amber-300"
      )}
    >
      {safe ? "Safe" : "Requires approval"}
    </span>
  );
}

const APPROVAL_STYLES: Record<string, string> = {
  pending: "border-amber-400/30 bg-amber-400/10 text-amber-300",
  approved: "border-emerald-400/30 bg-emerald-400/10 text-emerald-300",
  rejected: "border-rose-400/30 bg-rose-400/10 text-rose-300",
  expired: "border-ink-600 bg-ink-700/40 text-ink-400",
};

export function ApprovalStatusBadge({ status }: { status: string }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium capitalize",
        APPROVAL_STYLES[status] ?? "border-ink-600 bg-ink-700/40 text-ink-300"
      )}
    >
      {status}
    </span>
  );
}

export function ModeBadge({ mode }: { mode: string }) {
  const gated = mode === "approval_gated";
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium",
        gated
          ? "border-brand-400/30 bg-brand-400/10 text-brand-300"
          : "border-ink-600 bg-ink-700/40 text-ink-300"
      )}
    >
      {gated ? "approval-gated" : "free-running"}
    </span>
  );
}
