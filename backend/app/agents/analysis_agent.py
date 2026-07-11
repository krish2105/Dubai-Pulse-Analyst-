"""
Analysis Agent
==============

Deterministic quantitative analysis over the Query Agent's result set. **No LLM**
— every number here is computed in Python from the queried data, which is exactly
what makes the downstream Verifier meaningful (the narrative must match these
numbers, and these numbers provably come from the data).

Capabilities
------------
* KPI summary stats on numeric columns (min / max / mean / median).
* Trend analysis when a time dimension is present: start→end % change, direction,
  and rolling z-score **anomaly flags** (> 2σ from the trailing mean).
* Ranking / decomposition when a categorical dimension is present: top & bottom
  movers/levels by the primary metric.
* A list of deterministic ``facts`` (strings with exact numbers) that feed the
  Narrative Agent and are cross-checked by the Verifier.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from app.agents.events import emit_event

logger = logging.getLogger("dubaipulse.analysis_agent")

# Columns that represent a time axis, most-granular first.
_TIME_COLS = ["month_date", "year_month", "quarter", "year", "month"]
# Columns that are categorical dimensions worth ranking by.
_CATEGORY_COLS = ["zone", "community", "transaction_type", "property_type",
                  "property_category", "developer", "view", "metro_line", "payment_plan"]


class AnalysisAgent:
    async def run(self, question: str, query_result: dict) -> dict:
        await emit_event("analysis_agent", "running", "Detecting trends, anomalies and rankings…")

        rows = query_result.get("rows", [])
        columns = query_result.get("columns", [])
        if not rows:
            await emit_event("analysis_agent", "complete", "No rows to analyse.")
            return {"facts": [], "kpis": {}, "trend": None, "ranking": None,
                    "notes": ["Query returned no rows; nothing to analyse."]}

        df = pd.DataFrame(rows, columns=columns)
        numeric_cols = self._numeric_cols(df)
        time_col = next((c for c in _TIME_COLS if c in df.columns), None)
        cat_cols = [c for c in _CATEGORY_COLS if c in df.columns]

        kpis = self._kpis(df, numeric_cols)
        trend = self._trend(df, time_col, numeric_cols)
        ranking = self._ranking(df, cat_cols, numeric_cols, time_col)

        facts = self._facts(df, numeric_cols, time_col, cat_cols, trend, ranking)
        notes = self._notes(question, df)

        anomaly_count = len(trend["anomalies"]) if trend else 0
        detail = (
            f"Analysed {len(df)} row(s)"
            + (f" · {anomaly_count} anomaly month(s) flagged" if trend else "")
            + (f" · ranked by {ranking['metric']}" if ranking else "")
        )
        await emit_event(
            "analysis_agent", "complete", detail,
            fact_count=len(facts), has_trend=bool(trend),
            anomalies=anomaly_count, facts=facts[:8],
        )
        return {"facts": facts, "kpis": kpis, "trend": trend, "ranking": ranking, "notes": notes}

    # ------------------------------------------------------------------ #
    @staticmethod
    def _numeric_cols(df: pd.DataFrame) -> list[str]:
        cols = []
        for c in df.columns:
            if c in ("year", "month"):  # time-ish ints, not metrics
                continue
            s = pd.to_numeric(df[c], errors="coerce")
            if s.notna().sum() >= max(1, int(0.6 * len(df))):
                cols.append(c)
        return cols

    def _kpis(self, df: pd.DataFrame, numeric_cols: list[str]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for c in numeric_cols:
            s = pd.to_numeric(df[c], errors="coerce").dropna()
            if s.empty:
                continue
            out[c] = {
                "min": round(float(s.min()), 2),
                "max": round(float(s.max()), 2),
                "mean": round(float(s.mean()), 2),
                "median": round(float(s.median()), 2),
            }
        return out

    def _trend(self, df: pd.DataFrame, time_col: str | None, numeric_cols: list[str]) -> dict | None:
        if not time_col or not numeric_cols or len(df) < 3:
            return None
        metric = numeric_cols[0]
        t = df[[time_col, metric]].copy()
        t[metric] = pd.to_numeric(t[metric], errors="coerce")
        t = t.dropna()
        if len(t) < 3:
            return None
        # One value per time point (mean if the query returned several).
        series = t.groupby(time_col)[metric].mean().sort_index()
        if len(series) < 3:
            return None

        start_v, end_v = float(series.iloc[0]), float(series.iloc[-1])
        pct = round((end_v - start_v) / start_v * 100, 2) if start_v else None
        direction = "flat"
        if pct is not None:
            direction = "up" if pct > 1 else "down" if pct < -1 else "flat"

        # Rolling z-score anomaly detection: compare each point against the window
        # of PRECEDING points (shift(1)) so a spike can't hide inside its own window.
        window = min(6, max(3, len(series) // 3))
        prior = series.shift(1)
        roll_mean = prior.rolling(window, min_periods=window).mean()
        roll_std = prior.rolling(window, min_periods=window).std(ddof=0)
        z = (series - roll_mean) / roll_std.replace(0, np.nan)
        anomalies = [
            {"t": str(idx), "value": round(float(series.loc[idx]), 2), "z": round(float(zz), 2)}
            for idx, zz in z.items()
            if pd.notna(zz) and abs(zz) > 2
        ]

        return {
            "metric": metric,
            "time_col": time_col,
            "start": {"t": str(series.index[0]), "value": round(start_v, 2)},
            "end": {"t": str(series.index[-1]), "value": round(end_v, 2)},
            "pct_change": pct,
            "direction": direction,
            "points": [{"t": str(i), "value": round(float(v), 2)} for i, v in series.items()],
            "anomalies": anomalies,
        }

    def _ranking(self, df: pd.DataFrame, cat_cols: list[str], numeric_cols: list[str],
                 time_col: str | None) -> dict | None:
        if not cat_cols or not numeric_cols:
            return None
        cat = cat_cols[0]
        metric = numeric_cols[0]
        g = df.copy()
        g[metric] = pd.to_numeric(g[metric], errors="coerce")
        agg = g.groupby(cat)[metric].mean().dropna().sort_values(ascending=False)
        if agg.empty or agg.nunique() < 2:
            return None
        top = [{"key": str(k), "value": round(float(v), 2)} for k, v in agg.head(5).items()]
        bottom = [{"key": str(k), "value": round(float(v), 2)} for k, v in agg.tail(5).items()]
        return {"category": cat, "metric": metric, "top": top, "bottom": bottom}

    def _facts(self, df, numeric_cols, time_col, cat_cols, trend, ranking) -> list[str]:
        """Deterministic natural-language facts with exact numbers."""
        facts: list[str] = []

        if trend and trend["pct_change"] is not None:
            facts.append(
                f"{trend['metric']} moved from {trend['start']['value']:,} "
                f"({trend['start']['t']}) to {trend['end']['value']:,} ({trend['end']['t']}), "
                f"a change of {trend['pct_change']}% ({trend['direction']})."
            )
            for a in trend["anomalies"][:4]:
                facts.append(
                    f"Anomaly: {trend['metric']} at {a['t']} was {a['value']:,} "
                    f"(z-score {a['z']}), an unusual deviation from trend."
                )

        if ranking:
            top = ranking["top"]
            if top:
                facts.append(
                    f"Highest {ranking['metric']} by {ranking['category']}: "
                    + ", ".join(f"{r['key']} ({r['value']:,})" for r in top[:3]) + "."
                )
            bottom = ranking["bottom"]
            if bottom and len(ranking["top"]) + len(bottom) > 2:
                facts.append(
                    f"Lowest {ranking['metric']} by {ranking['category']}: "
                    + ", ".join(f"{r['key']} ({r['value']:,})" for r in bottom[:3]) + "."
                )

        # Single-value answers (simple lookups) become a fact too.
        if not facts and numeric_cols and len(df) == 1:
            for c in numeric_cols:
                val = pd.to_numeric(df[c], errors="coerce").iloc[0]
                if pd.notna(val):
                    facts.append(f"{c} = {round(float(val), 2):,}.")

        # Generic KPI facts as a fallback so the narrative always has anchors.
        if not facts and numeric_cols:
            c = numeric_cols[0]
            s = pd.to_numeric(df[c], errors="coerce").dropna()
            if not s.empty:
                facts.append(
                    f"{c}: mean {round(float(s.mean()), 2):,}, "
                    f"median {round(float(s.median()), 2):,}, "
                    f"range {round(float(s.min()), 2):,}–{round(float(s.max()), 2):,}."
                )
        return facts

    @staticmethod
    def _notes(question: str, df: pd.DataFrame) -> list[str]:
        notes: list[str] = []
        q = question.lower()
        if "yield" in q:
            notes.append("Yields are GROSS (rent ÷ price); service charges are not in the dataset.")
        if any(w in q for w in ("why", "cause", "because", "driver", "reason", "spike", "drove")):
            notes.append("Relationships shown are correlations, not proven causation.")
        return notes
