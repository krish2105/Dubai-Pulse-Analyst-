"""
Dashboard insights endpoint.

Returns headline KPIs + a few chart-ready series for the KpiDashboard, computed
directly from the processed data via DuckDB. Values are static for a given
dataset, so we cache them for the process lifetime.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from fastapi import APIRouter

from app.tools.duckdb_engine import get_engine

router = APIRouter(tags=["insights"])


@lru_cache
def _compute_kpis() -> dict[str, Any]:
    e = get_engine()

    def q(sql: str) -> list[dict]:
        return e.run_query(sql).rows

    headline = q(
        """
        SELECT
          count(*)                                             AS total_listings,
          count(*) FILTER (WHERE transaction_type='secondary') AS secondary,
          count(*) FILTER (WHERE transaction_type='offplan')   AS offplan,
          count(*) FILTER (WHERE transaction_type='rental')    AS rental,
          count(DISTINCT community)                            AS communities,
          count(DISTINCT zone)                                 AS zones,
          min(date_listed)                                     AS start_date,
          max(date_listed)                                     AS end_date
        FROM transactions
        """
    )[0]

    # Market-wide monthly secondary price/sqft + base rate (chart series).
    price_trend = q(
        """
        SELECT year_month,
               ROUND(AVG(secondary_price_per_sqft_usd)) AS price_per_sqft,
               ROUND(AVG(cbuae_base_rate_pct), 2)       AS base_rate
        FROM area_monthly
        GROUP BY year_month
        ORDER BY year_month
        """
    )

    # Transaction volume by year (all types).
    volume_by_year = q(
        """
        SELECT year,
               count(*) FILTER (WHERE transaction_type='secondary') AS secondary,
               count(*) FILTER (WHERE transaction_type='offplan')   AS offplan,
               count(*) FILTER (WHERE transaction_type='rental')    AS rental
        FROM transactions
        WHERE year IS NOT NULL
        GROUP BY year ORDER BY year
        """
    )

    # Top zones by average secondary price/sqft (most recent full context).
    top_zones = q(
        """
        SELECT zone, ROUND(AVG(price_per_sqft_usd)) AS price_per_sqft
        FROM transactions
        WHERE transaction_type='secondary' AND year=2025
        GROUP BY zone ORDER BY price_per_sqft DESC LIMIT 8
        """
    )

    # Top communities by gross rental yield in 2025.
    top_yield = q(
        """
        SELECT community, ROUND(AVG(rental_yield_pct), 2) AS yield_pct
        FROM area_monthly
        WHERE year=2025
        GROUP BY community ORDER BY yield_pct DESC LIMIT 8
        """
    )

    return {
        "headline": headline,
        "price_trend": price_trend,
        "volume_by_year": volume_by_year,
        "top_zones": top_zones,
        "top_yield": top_yield,
    }


@router.get("/insights")
async def insights() -> dict:
    return _compute_kpis()
