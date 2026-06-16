"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { AgentRun } from "@/types";

interface RunChartsProps {
  runs: AgentRun[];
}

const AXIS = "#64748b";
const GRID = "#1e293b";

/** Cost-per-run (bar) + latency-per-run (line) charts over recent runs. */
export default function RunCharts({ runs }: RunChartsProps) {
  // Oldest -> newest so the x-axis reads left-to-right chronologically.
  const data = [...runs]
    .sort((a, b) => a.created_at - b.created_at)
    .map((r) => ({
      id: r.id,
      label: r.id.slice(0, 6),
      cost: Number((r.cost?.estimated_cost ?? 0).toFixed(6)),
      latency: Number((r.trace?.duration_ms ?? 0).toFixed(1)),
      status: r.status,
    }));

  if (data.length === 0) return null;

  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <div className="card">
        <h3 className="mb-1 text-sm font-semibold text-ink-200">
          Cost per run
        </h3>
        <p className="mb-4 text-xs text-ink-500">Estimated USD, by run id</p>
        <div data-testid="cost-chart" className="h-56 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
              <XAxis dataKey="label" stroke={AXIS} fontSize={11} tickLine={false} />
              <YAxis
                stroke={AXIS}
                fontSize={11}
                tickLine={false}
                axisLine={false}
                width={56}
                tickFormatter={(v) => `$${Number(v).toFixed(4)}`}
              />
              <Tooltip
                contentStyle={{
                  background: "#0f172a",
                  border: "1px solid #1e293b",
                  borderRadius: 8,
                  color: "#e2e8f0",
                  fontSize: 12,
                }}
                formatter={(v: number) => [`$${Number(v).toFixed(5)}`, "Cost"]}
              />
              <Bar dataKey="cost" radius={[4, 4, 0, 0]}>
                {data.map((d) => (
                  <Cell
                    key={d.id}
                    fill={d.status === "error" ? "#f43f5e" : "#6366f1"}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="card">
        <h3 className="mb-1 text-sm font-semibold text-ink-200">
          Latency per run
        </h3>
        <p className="mb-4 text-xs text-ink-500">Total trace duration (ms)</p>
        <div data-testid="latency-chart" className="h-56 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
              <XAxis dataKey="label" stroke={AXIS} fontSize={11} tickLine={false} />
              <YAxis
                stroke={AXIS}
                fontSize={11}
                tickLine={false}
                axisLine={false}
                width={48}
                tickFormatter={(v) => `${v}ms`}
              />
              <Tooltip
                contentStyle={{
                  background: "#0f172a",
                  border: "1px solid #1e293b",
                  borderRadius: 8,
                  color: "#e2e8f0",
                  fontSize: 12,
                }}
                formatter={(v: number) => [`${Number(v).toFixed(1)} ms`, "Latency"]}
              />
              <Line
                type="monotone"
                dataKey="latency"
                stroke="#818cf8"
                strokeWidth={2}
                dot={{ r: 3, fill: "#818cf8" }}
                activeDot={{ r: 5 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
