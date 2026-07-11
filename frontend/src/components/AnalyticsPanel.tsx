// AnalyticsPanel — deeper analytics: price distribution, base-rate↔price and
// yield↔price correlations, seasonality, and price by unit type.

import { useQuery } from "@tanstack/react-query";
import {
  Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Scatter, ScatterChart,
  Tooltip, XAxis, YAxis, ZAxis,
} from "recharts";
import { fetchAnalytics } from "../lib/api";
import { useTheme } from "../hooks/useTheme";
import type { Analytics } from "../lib/types";

const MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function useChartColors() {
  const { theme } = useTheme();
  const dark = theme === "dark";
  return {
    grid: "#94a3b833",
    tick: dark ? "#64748b" : "#8a94a6",
    tip: {
      contentStyle: {
        background: dark ? "#0f1524" : "#ffffff",
        border: `1px solid ${dark ? "#1e263c" : "#dfe3ec"}`,
        borderRadius: 8, fontSize: 12, color: dark ? "#e2e8f0" : "#1f2937",
      },
      labelStyle: { color: dark ? "#64748b" : "#8a94a6" },
    },
  };
}

function Card({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-line bg-surface/60 p-3">
      <div className="mb-2">
        <div className="text-xs font-medium text-content">{title}</div>
        {subtitle && <div className="text-[10px] text-faint">{subtitle}</div>}
      </div>
      <div className="h-40">
        <ResponsiveContainer width="100%" height="100%">{children as any}</ResponsiveContainer>
      </div>
    </div>
  );
}

export default function AnalyticsPanel() {
  const c = useChartColors();
  const { data, isLoading, isError } = useQuery<Analytics>({ queryKey: ["analytics"], queryFn: fetchAnalytics });

  if (isLoading) return <div className="p-4 text-sm text-faint">Loading analytics…</div>;
  if (isError || !data) return <div className="p-4 text-sm text-rose-500">Could not load analytics.</div>;

  const season = data.seasonality.map((s) => ({ month: MONTHS[s.month] || s.month, avg_mom_pct: s.avg_mom_pct }));

  return (
    <div className="space-y-3 p-4">
      <div>
        <h3 className="text-sm font-semibold text-bright">Deep analytics</h3>
        <p className="text-[11px] text-faint">Distributions, correlations & seasonality</p>
      </div>

      <Card title="Secondary price/sqft distribution" subtitle="USD/sqft buckets, listing count">
        <BarChart data={data.price_distribution} margin={{ top: 4, right: 6, left: -18, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={c.grid} vertical={false} />
          <XAxis dataKey="bin" tick={{ fontSize: 8, fill: c.tick }} interval={3} />
          <YAxis tick={{ fontSize: 9, fill: c.tick }} />
          <Tooltip {...c.tip} />
          <Bar isAnimationActive={false} dataKey="n" fill="#2f7bff" radius={[2, 2, 0, 0]} name="Listings" />
        </BarChart>
      </Card>

      <Card title="CBUAE base rate ↔ price/sqft" subtitle="each point = a month (correlation, not causation)">
        <ScatterChart margin={{ top: 4, right: 8, left: -18, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={c.grid} />
          <XAxis type="number" dataKey="base_rate" name="Base rate %" unit="%" tick={{ fontSize: 9, fill: c.tick }} />
          <YAxis type="number" dataKey="price_per_sqft" name="Price/sqft" tick={{ fontSize: 9, fill: c.tick }} />
          <Tooltip {...c.tip} cursor={{ strokeDasharray: "3 3" }} />
          <Scatter isAnimationActive={false} data={data.rate_vs_price} fill="#e0a92e" fillOpacity={0.6} />
        </ScatterChart>
      </Card>

      <Card title="Yield ↔ price by community (2025)" subtitle="higher price often = lower relative yield">
        <ScatterChart margin={{ top: 4, right: 8, left: -18, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={c.grid} />
          <XAxis type="number" dataKey="price_per_sqft" name="Price/sqft" tick={{ fontSize: 9, fill: c.tick }} />
          <YAxis type="number" dataKey="yield_pct" name="Yield %" unit="%" tick={{ fontSize: 9, fill: c.tick }} domain={["auto", "auto"]} />
          <ZAxis range={[30, 30]} />
          <Tooltip {...c.tip} cursor={{ strokeDasharray: "3 3" }} />
          <Scatter isAnimationActive={false} data={data.yield_vs_price} fill="#22d3ee" fillOpacity={0.6} />
        </ScatterChart>
      </Card>

      <Card title="Seasonality" subtitle="avg month-over-month price change by calendar month">
        <BarChart data={season} margin={{ top: 4, right: 6, left: -18, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={c.grid} vertical={false} />
          <XAxis dataKey="month" tick={{ fontSize: 8, fill: c.tick }} />
          <YAxis tick={{ fontSize: 9, fill: c.tick }} />
          <Tooltip {...c.tip} />
          <Bar isAnimationActive={false} dataKey="avg_mom_pct" radius={[2, 2, 0, 0]} name="MoM %">
            {season.map((s, i) => (
              <Cell key={i} fill={s.avg_mom_pct >= 0 ? "#34d399" : "#f87171"} />
            ))}
          </Bar>
        </BarChart>
      </Card>

      <Card title="Price/sqft by unit type" subtitle="secondary sales">
        <BarChart data={data.price_by_type} layout="vertical" margin={{ top: 0, right: 12, left: 30, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={c.grid} horizontal={false} />
          <XAxis type="number" tick={{ fontSize: 9, fill: c.tick }} />
          <YAxis type="category" dataKey="property_type" tick={{ fontSize: 8, fill: c.tick }} width={70} />
          <Tooltip {...c.tip} />
          <Bar isAnimationActive={false} dataKey="price_per_sqft" fill="#e0a92e" radius={[0, 3, 3, 0]} name="USD/sqft" />
        </BarChart>
      </Card>
    </div>
  );
}
