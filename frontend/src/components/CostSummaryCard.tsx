import { Coins, Gauge, Hash, Layers } from "lucide-react";
import type { CostSummary } from "@/types";
import { formatCost, formatMs, formatTokens } from "@/lib/format";

/** Compact cost / token / latency summary for a single run. */
export default function CostSummaryCard({ cost }: { cost: CostSummary }) {
  const stats = [
    {
      icon: Coins,
      label: "Cost",
      value: formatCost(cost.total_cost ?? cost.estimated_cost ?? 0),
    },
    {
      icon: Hash,
      label: "Tokens",
      value: formatTokens(cost.total_tokens ?? 0),
    },
    {
      icon: Layers,
      label: "LLM calls",
      value: String(cost.total_calls ?? cost.total_requests ?? 0),
    },
    {
      icon: Gauge,
      label: "Avg latency",
      value: formatMs(cost.average_latency_ms ?? 0),
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {stats.map(({ icon: Icon, label, value }) => (
        <div key={label} className="stat-card">
          <div className="mb-1 flex items-center gap-1.5 text-xs text-ink-500">
            <Icon className="h-3.5 w-3.5" />
            {label}
          </div>
          <div className="mono text-lg font-semibold text-ink-100">{value}</div>
        </div>
      ))}
    </div>
  );
}
