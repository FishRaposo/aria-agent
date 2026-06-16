import { FlaskConical } from "lucide-react";

interface DemoBadgeProps {
  reason?: string;
  className?: string;
}

/** Visible indicator shown whenever a view is rendering bundled mock data. */
export default function DemoBadge({ reason, className = "" }: DemoBadgeProps) {
  return (
    <span
      data-testid="demo-badge"
      title={reason || "Backend unreachable — showing bundled demo data"}
      className={`inline-flex items-center gap-1.5 rounded-full border border-amber-400/40 bg-amber-400/10 px-2.5 py-0.5 text-xs font-medium text-amber-300 ${className}`}
    >
      <FlaskConical className="h-3.5 w-3.5" />
      Demo mode
    </span>
  );
}
