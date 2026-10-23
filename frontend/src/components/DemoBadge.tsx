import { Database } from "lucide-react";
export default function DemoBadge({ reason, className = "" }: { reason?: string; forced?: boolean; className?: string }) {
  return <span data-testid="demo-badge" title={reason || "Interactive sample data"} className={`inline-flex items-center gap-1.5 rounded-full border border-brand-400/30 bg-brand-500/10 px-2.5 py-0.5 text-xs font-medium text-brand-200 ${className}`}><Database className="h-3.5 w-3.5" />Sample data</span>;
}
