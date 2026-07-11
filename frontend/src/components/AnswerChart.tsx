// AnswerChart — renders a small chart inside an answer, straight from the
// Analysis Agent's output: a trend line if the answer has a time series, else a
// ranking bar. Theme-aware. Returns null when there's nothing chartable.

import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { useTheme } from "../hooks/useTheme";
import type { FinalAnswer } from "../lib/types";

const pretty = (m: string) => (m || "").replace(/_/g, " ");

export default function AnswerChart({ final }: { final: FinalAnswer }) {
  const { theme } = useTheme();
  const dark = theme === "dark";
  const grid = "#94a3b833";
  const tick = dark ? "#64748b" : "#8a94a6";
  const tip = {
    contentStyle: {
      background: dark ? "#0f1524" : "#ffffff",
      border: `1px solid ${dark ? "#1e263c" : "#dfe3ec"}`,
      borderRadius: 8, fontSize: 12, color: dark ? "#e2e8f0" : "#1f2937",
    },
    labelStyle: { color: tick },
  };

  const trend = final.trend;
  const ranking = final.ranking;

  if (trend && Array.isArray(trend.points) && trend.points.length >= 3) {
    const data = trend.points.map((p: any) => ({ t: String(p.t), value: p.value }));
    const pct = trend.pct_change;
    return (
      <div className="mt-3 rounded-lg border border-line bg-surface/50 p-3">
        <div className="mb-1 text-[11px] font-medium text-muted">
          {pretty(trend.metric)} over time
          {pct != null ? ` · ${pct > 0 ? "+" : ""}${pct}%` : ""}
        </div>
        <div className="h-40">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 4, right: 8, left: -14, bottom: 0 }}>
              <defs>
                <linearGradient id="ansGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#e0a92e" stopOpacity={0.5} />
                  <stop offset="100%" stopColor="#e0a92e" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={grid} />
              <XAxis dataKey="t" tick={{ fontSize: 9, fill: tick }}
                     interval={Math.max(0, Math.floor(data.length / 6))} />
              <YAxis tick={{ fontSize: 9, fill: tick }} width={40} />
              <Tooltip {...tip} />
              <Area isAnimationActive={false} type="monotone" dataKey="value" stroke="#e0a92e"
                    fill="url(#ansGrad)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    );
  }

  if (ranking && Array.isArray(ranking.top) && ranking.top.length >= 2) {
    const data = ranking.top.map((r: any) => ({ key: String(r.key), value: r.value }));
    return (
      <div className="mt-3 rounded-lg border border-line bg-surface/50 p-3">
        <div className="mb-1 text-[11px] font-medium text-muted">Top by {pretty(ranking.metric)}</div>
        <div className="h-44">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} layout="vertical" margin={{ top: 0, right: 12, left: 8, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={grid} horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 9, fill: tick }} />
              <YAxis type="category" dataKey="key" tick={{ fontSize: 9, fill: tick }} width={92} />
              <Tooltip {...tip} />
              <Bar isAnimationActive={false} dataKey="value" fill="#e0a92e" radius={[0, 3, 3, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    );
  }

  return null;
}
