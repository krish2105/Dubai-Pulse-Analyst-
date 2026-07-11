// KpiDashboard — headline dataset KPIs + chart-ready series from /insights.
// Gives the copilot a market-overview companion panel.

import { useQuery } from "@tanstack/react-query";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Line, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import { Building2, TrendingUp, Percent, Layers } from "lucide-react";
import { fetchInsights } from "../lib/api";
import type { Insights } from "../lib/types";

const fmt = (n: number) => new Intl.NumberFormat("en-US").format(n);

function StatCard({ icon: Icon, label, value, sub }: any) {
  return (
    <div className="rounded-xl border border-line bg-surface/60 p-3">
      <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-wide text-faint">
        <Icon className="h-3.5 w-3.5 text-accent-blue" /> {label}
      </div>
      <div className="mt-1 text-xl font-semibold text-bright">{value}</div>
      {sub && <div className="text-[11px] text-faint">{sub}</div>}
    </div>
  );
}

function ChartCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-line bg-surface/60 p-3">
      <div className="mb-2 text-xs font-medium text-content">{title}</div>
      <div className="h-40">
        <ResponsiveContainer width="100%" height="100%">{children as any}</ResponsiveContainer>
      </div>
    </div>
  );
}

const tooltipStyle = {
  contentStyle: { background: "#0f1524", border: "1px solid #1e263c", borderRadius: 8, fontSize: 12 },
  labelStyle: { color: "#94a3b8" },
};

export default function KpiDashboard() {
  const { data, isLoading, isError } = useQuery<Insights>({
    queryKey: ["insights"],
    queryFn: fetchInsights,
  });

  if (isLoading) {
    return <div className="p-4 text-sm text-faint">Loading market overview…</div>;
  }
  if (isError || !data) {
    return <div className="p-4 text-sm text-rose-300">Could not load market overview. Is the backend running?</div>;
  }

  const h = data.headline;

  return (
    <div className="space-y-3 p-4">
      <div>
        <h3 className="text-sm font-semibold text-bright">Market overview</h3>
        <p className="text-[11px] text-faint">
          {fmt(h.total_listings)} listings · {h.communities} communities · {h.zones} zones ·{" "}
          {h.start_date?.slice(0, 7)} → {h.end_date?.slice(0, 7)}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <StatCard icon={Building2} label="Secondary" value={fmt(h.secondary)} sub="sales listings" />
        <StatCard icon={Layers} label="Off-plan" value={fmt(h.offplan)} sub="listings" />
        <StatCard icon={TrendingUp} label="Rentals" value={fmt(h.rental)} sub="listings" />
        <StatCard
          icon={Percent}
          label="Top yield"
          value={`${data.top_yield[0]?.yield_pct ?? "–"}%`}
          sub={data.top_yield[0]?.community}
        />
      </div>

      <ChartCard title="Market price / sqft (USD) & CBUAE base rate">
        <AreaChart data={data.price_trend} margin={{ top: 4, right: 6, left: -18, bottom: 0 }}>
          <defs>
            <linearGradient id="ppsf" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#e0a92e" stopOpacity={0.5} />
              <stop offset="100%" stopColor="#e0a92e" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#94a3b833" />
          <XAxis dataKey="year_month" tick={{ fontSize: 9, fill: "#64748b" }} interval={11} />
          <YAxis yAxisId="l" tick={{ fontSize: 9, fill: "#64748b" }} />
          <YAxis yAxisId="r" orientation="right" tick={{ fontSize: 9, fill: "#64748b" }} width={26} />
          <Tooltip {...tooltipStyle} />
          <Area isAnimationActive={false} yAxisId="l" type="monotone" dataKey="price_per_sqft" stroke="#e0a92e" fill="url(#ppsf)" strokeWidth={2} name="Price/sqft" />
          <Line isAnimationActive={false} yAxisId="r" type="monotone" dataKey="base_rate" stroke="#2f7bff" strokeWidth={1.5} dot={false} name="Base rate %" />
        </AreaChart>
      </ChartCard>

      <ChartCard title="Transaction volume by year">
        <BarChart data={data.volume_by_year} margin={{ top: 4, right: 6, left: -18, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#94a3b833" />
          <XAxis dataKey="year" tick={{ fontSize: 9, fill: "#64748b" }} />
          <YAxis tick={{ fontSize: 9, fill: "#64748b" }} />
          <Tooltip {...tooltipStyle} />
          <Bar isAnimationActive={false} dataKey="secondary" stackId="a" fill="#2f7bff" name="Secondary" />
          <Bar isAnimationActive={false} dataKey="offplan" stackId="a" fill="#e0a92e" name="Off-plan" />
          <Bar isAnimationActive={false} dataKey="rental" stackId="a" fill="#22d3ee" name="Rental" radius={[2, 2, 0, 0]} />
        </BarChart>
      </ChartCard>

      <ChartCard title="Top zones · secondary price/sqft (2025)">
        <BarChart data={data.top_zones} layout="vertical" margin={{ top: 0, right: 8, left: 40, bottom: 0 }}>
          <XAxis type="number" tick={{ fontSize: 9, fill: "#64748b" }} />
          <YAxis type="category" dataKey="zone" tick={{ fontSize: 9, fill: "#94a3b8" }} width={80} />
          <Tooltip {...tooltipStyle} />
          <Bar isAnimationActive={false} dataKey="price_per_sqft" fill="#e0a92e" radius={[0, 3, 3, 0]} name="USD/sqft" />
        </BarChart>
      </ChartCard>

      <ChartCard title="Top communities · gross rental yield (2025)">
        <BarChart data={data.top_yield} layout="vertical" margin={{ top: 0, right: 8, left: 40, bottom: 0 }}>
          <XAxis type="number" tick={{ fontSize: 9, fill: "#64748b" }} />
          <YAxis type="category" dataKey="community" tick={{ fontSize: 9, fill: "#94a3b8" }} width={80} />
          <Tooltip {...tooltipStyle} />
          <Bar isAnimationActive={false} dataKey="yield_pct" fill="#22d3ee" radius={[0, 3, 3, 0]} name="Yield %" />
        </BarChart>
      </ChartCard>
    </div>
  );
}
