// ForecastChart — market price/sqft history + a 6-month projection with a ±2σ
// confidence band. Honest, explainable linear-trend + seasonality model.

import { useQuery } from "@tanstack/react-query";
import {
  Area, ComposedChart, CartesianGrid, Line, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { TrendingUp } from "lucide-react";
import { fetchForecast } from "../lib/api";
import { useTheme } from "../hooks/useTheme";
import type { Forecast } from "../lib/types";

export default function ForecastChart() {
  const { theme } = useTheme();
  const dark = theme === "dark";
  const { data, isLoading, isError } = useQuery<Forecast>({ queryKey: ["forecast"], queryFn: () => fetchForecast(6) });

  if (isLoading) return <div className="p-4 text-sm text-faint">Loading forecast…</div>;
  if (isError || !data) return null;

  const merged: any[] = [
    ...data.history.map((h) => ({ date: h.date, actual: h.value })),
    ...data.forecast.map((f) => ({
      date: f.date, forecast: f.value, lower: f.lower, band: +(f.upper - f.lower).toFixed(1),
    })),
  ];
  // Connect the forecast line + band to the last actual point.
  if (data.history.length && data.forecast.length) {
    const last = merged[data.history.length - 1];
    last.forecast = last.actual;
    last.lower = last.actual;
    last.band = 0;
  }

  const tick = dark ? "#64748b" : "#8a94a6";
  const tip = {
    contentStyle: {
      background: dark ? "#0f1524" : "#ffffff",
      border: `1px solid ${dark ? "#1e263c" : "#dfe3ec"}`,
      borderRadius: 8, fontSize: 12, color: dark ? "#e2e8f0" : "#1f2937",
    },
    labelStyle: { color: tick },
  };

  return (
    <div className="rounded-xl border border-line bg-surface/60 p-3">
      <div className="mb-2 flex items-center gap-1.5">
        <TrendingUp className="h-3.5 w-3.5 text-accent-gold" />
        <div>
          <div className="text-xs font-medium text-content">Price/sqft forecast · {data.label}</div>
          <div className="text-[10px] text-faint">
            {data.method} · trend {data.trend_per_month > 0 ? "+" : ""}{data.trend_per_month}/mo
          </div>
        </div>
      </div>
      <div className="h-44">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={merged} margin={{ top: 4, right: 6, left: -18, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#94a3b833" />
            <XAxis dataKey="date" tick={{ fontSize: 8, fill: tick }} interval={11} />
            <YAxis tick={{ fontSize: 9, fill: tick }} domain={["auto", "auto"]} />
            <Tooltip {...tip} />
            {/* Confidence band via stacked areas (invisible base + shaded band). */}
            <Area isAnimationActive={false} stackId="band" dataKey="lower" stroke="none" fill="transparent" />
            <Area isAnimationActive={false} stackId="band" dataKey="band" stroke="none" fill="#e0a92e" fillOpacity={0.15} name="±2σ" />
            <Line isAnimationActive={false} dataKey="actual" stroke="#2f7bff" strokeWidth={2} dot={false} name="Actual" />
            <Line isAnimationActive={false} dataKey="forecast" stroke="#e0a92e" strokeWidth={2} strokeDasharray="5 4" dot={false} name="Forecast" />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
