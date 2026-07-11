// MapPanel — interactive Dubai map. Each community is a circle coloured by the
// selected metric (price/sqft or gross yield) and sized by transaction volume.
// Uses free OSM/Carto tiles (no API token). Theme-aware basemap.

import { useMemo, useState } from "react";
import { CircleMarker, MapContainer, TileLayer, Tooltip } from "react-leaflet";
import { useQuery } from "@tanstack/react-query";
import "leaflet/dist/leaflet.css";
import { fetchGeo } from "../lib/api";
import { useTheme } from "../hooks/useTheme";
import type { GeoPoint } from "../lib/types";

type Metric = "price" | "yield";

// Interpolate blue (low) → gold (high).
function colorFor(t: number): string {
  const clamp = Math.max(0, Math.min(1, t));
  const c1 = [47, 123, 255]; // brand blue
  const c2 = [224, 169, 46]; // gold
  const r = Math.round(c1[0] + (c2[0] - c1[0]) * clamp);
  const g = Math.round(c1[1] + (c2[1] - c1[1]) * clamp);
  const b = Math.round(c1[2] + (c2[2] - c1[2]) * clamp);
  return `rgb(${r}, ${g}, ${b})`;
}

export default function MapPanel() {
  const { theme } = useTheme();
  const [metric, setMetric] = useState<Metric>("price");
  const { data, isLoading, isError } = useQuery<GeoPoint[]>({ queryKey: ["geo"], queryFn: fetchGeo });

  const { points, min, max } = useMemo(() => {
    const pts = (data || []).filter((p) =>
      metric === "price" ? p.price_per_sqft != null : p.yield_pct != null,
    );
    const vals = pts.map((p) => (metric === "price" ? p.price_per_sqft! : p.yield_pct!));
    return { points: pts, min: Math.min(...vals, 0), max: Math.max(...vals, 1) };
  }, [data, metric]);

  const tiles = theme === "dark"
    ? "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
    : "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png";

  if (isLoading) return <div className="p-4 text-sm text-faint">Loading map…</div>;
  if (isError || !data) return <div className="p-4 text-sm text-rose-500">Could not load the map.</div>;

  const maxVol = Math.max(...points.map((p) => p.n_secondary), 1);

  return (
    <div className="space-y-3 p-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-bright">Dubai price map</h3>
          <p className="text-[11px] text-faint">{points.length} communities · size = volume</p>
        </div>
        <div className="flex items-center rounded-lg border border-line p-0.5 text-xs">
          <button
            onClick={() => setMetric("price")}
            className={`rounded-md px-2 py-1 transition ${metric === "price" ? "bg-elevated text-bright" : "text-muted hover:text-bright"}`}
          >
            Price/sqft
          </button>
          <button
            onClick={() => setMetric("yield")}
            className={`rounded-md px-2 py-1 transition ${metric === "yield" ? "bg-elevated text-bright" : "text-muted hover:text-bright"}`}
          >
            Yield
          </button>
        </div>
      </div>

      <div className="overflow-hidden rounded-xl border border-line" style={{ height: 420 }}>
        <MapContainer
          center={[25.12, 55.23]}
          zoom={10}
          scrollWheelZoom={false}
          style={{ height: "100%", width: "100%", background: "transparent" }}
        >
          <TileLayer
            attribution='&copy; OpenStreetMap &copy; CARTO'
            url={tiles}
          />
          {points.map((p) => {
            const v = metric === "price" ? p.price_per_sqft! : p.yield_pct!;
            const t = (v - min) / (max - min || 1);
            const radius = 4 + Math.sqrt(p.n_secondary / maxVol) * 12;
            return (
              <CircleMarker
                key={p.community}
                center={[p.lat, p.lon]}
                radius={radius}
                pathOptions={{ color: colorFor(t), fillColor: colorFor(t), fillOpacity: 0.7, weight: 1 }}
              >
                <Tooltip>
                  <div style={{ fontSize: 12 }}>
                    <strong>{p.community}</strong> ({p.zone})<br />
                    {p.price_per_sqft ? `$${p.price_per_sqft.toLocaleString()}/sqft` : "—"}
                    {p.yield_pct != null ? ` · ${p.yield_pct}% yield` : ""}<br />
                    {p.n_secondary.toLocaleString()} listings
                  </div>
                </Tooltip>
              </CircleMarker>
            );
          })}
        </MapContainer>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-2 text-[11px] text-faint">
        <span>{metric === "price" ? "Lower $" : "Lower %"}</span>
        <div className="h-2 flex-1 rounded-full" style={{
          background: "linear-gradient(to right, rgb(47,123,255), rgb(224,169,46))",
        }} />
        <span>{metric === "price" ? "Higher $" : "Higher %"}</span>
      </div>
    </div>
  );
}
