"""
Lightweight, explainable price forecaster (no heavy ML deps).

Method: ordinary-least-squares **linear trend** + **month-of-year seasonality**
(mean residual per calendar month) + a ±2σ confidence band from the residuals.
Deterministic and easy to defend in an interview — and honest about being an
estimate, not a guarantee.
"""

from __future__ import annotations

import numpy as np


def _next_months(last_ym: str, horizon: int) -> list[str]:
    year, month = (int(x) for x in last_ym.split("-"))
    out = []
    for _ in range(horizon):
        month += 1
        if month > 12:
            month = 1
            year += 1
        out.append(f"{year:04d}-{month:02d}")
    return out


def forecast_series(months: list[str], values: list[float], horizon: int = 6) -> dict:
    """Return {history, forecast, method, trend_per_month}. ``months`` are 'YYYY-MM'."""
    n = len(values)
    history = [{"date": m, "value": round(float(v), 1)} for m, v in zip(months, values, strict=False)]
    if n < 6:
        return {"history": history, "forecast": [], "method": "insufficient-data", "trend_per_month": 0.0}

    y = np.array(values, dtype=float)

    # Fit the linear trend on a RECENT window so the forecast reflects the
    # current regime (e.g. post-2023 cooling) rather than the whole-history slope.
    window = min(n, 24)
    yw = y[-window:]
    tw = np.arange(window, dtype=float)
    slope, intercept = np.polyfit(tw, yw, 1)
    resid = yw - (slope * tw + intercept)

    # Month-of-year seasonal component (mean residual by calendar month, full history).
    full_t = np.arange(n, dtype=float)
    full_slope, full_int = np.polyfit(full_t, y, 1)
    full_resid = y - (full_slope * full_t + full_int)
    month_idx = np.array([int(m.split("-")[1]) for m in months])
    seasonal = {
        mth: float(full_resid[month_idx == mth].mean())
        for mth in range(1, 13) if (month_idx == mth).any()
    }

    sigma = float(np.std(resid)) if window > 2 else 0.0
    future_months = _next_months(months[-1], horizon)
    forecast = []
    for i, fm in enumerate(future_months, start=1):
        ft = window - 1 + i
        base = slope * ft + intercept
        seas = seasonal.get(int(fm.split("-")[1]), 0.0)
        val = base + seas
        # widen the band slightly with horizon
        band = 2 * sigma * (1 + 0.1 * i)
        forecast.append({
            "date": fm,
            "value": round(float(val), 1),
            "lower": round(float(val - band), 1),
            "upper": round(float(val + band), 1),
        })

    return {
        "history": history,
        "forecast": forecast,
        "method": "linear-trend + monthly-seasonality (±2σ)",
        "trend_per_month": round(float(slope), 2),
    }
