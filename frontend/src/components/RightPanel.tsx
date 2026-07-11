// RightPanel — tabbed companion panel: market Overview (KPIs), interactive Map,
// and deep Analytics.

import { useState } from "react";
import { BarChart3, LayoutDashboard, Map as MapIcon } from "lucide-react";
import KpiDashboard from "./KpiDashboard";
import MapPanel from "./MapPanel";
import AnalyticsPanel from "./AnalyticsPanel";

type Tab = "overview" | "map" | "analytics";

const TABS: { id: Tab; label: string; icon: any }[] = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "map", label: "Map", icon: MapIcon },
  { id: "analytics", label: "Analytics", icon: BarChart3 },
];

function initialTab(): Tab {
  try {
    const p = new URLSearchParams(location.search).get("panel");
    if (p === "map" || p === "analytics" || p === "overview") return p;
  } catch {
    /* ignore */
  }
  return "overview";
}

export default function RightPanel() {
  const [tab, setTab] = useState<Tab>(initialTab);
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-1 border-b border-line px-3 py-2">
        {TABS.map((t) => {
          const Icon = t.icon;
          return (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs transition ${
                tab === t.id ? "bg-elevated text-bright" : "text-muted hover:text-bright"
              }`}
            >
              <Icon className="h-3.5 w-3.5" /> {t.label}
            </button>
          );
        })}
      </div>
      <div className="flex-1 overflow-y-auto">
        {tab === "overview" && <KpiDashboard />}
        {tab === "map" && <MapPanel />}
        {tab === "analytics" && <AnalyticsPanel />}
      </div>
    </div>
  );
}
