import { AlertTriangle, Database } from "lucide-react";

interface DemoBadgeProps {
  reason?: string;
  /** True when NEXT_PUBLIC_DEMO_MODE forces sample data (not an outage fallback). */
  forced?: boolean;
  className?: string;
}

/** Visible indicator whenever a view renders bundled mock data. */
export default function DemoBadge({
  reason,
  forced = false,
  className = "",
}: DemoBadgeProps) {
  if (forced) {
    return (
      <span
        data-testid="demo-badge"
        title={reason || "Portfolio sample data"}
        className={`inline-flex items-center gap-1.5 rounded-full border border-ink-700 bg-ink-800/60 px-2.5 py-0.5 text-xs font-medium text-ink-400 ${className}`}
      >
        <Database className="h-3.5 w-3.5" />
        Sample data
      </span>
    );
  }

  return (
    <span
      data-testid="demo-badge"
      title={reason || "Backend unreachable — showing bundled demo data"}
      className={`inline-flex items-center gap-1.5 rounded-full border border-amber-400/40 bg-amber-400/10 px-2.5 py-0.5 text-xs font-medium text-amber-300 ${className}`}
    >
      <AlertTriangle className="h-3.5 w-3.5" />
      Backend offline — demo fallback
    </span>
  );
}
