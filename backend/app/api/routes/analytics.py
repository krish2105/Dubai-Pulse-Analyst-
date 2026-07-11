"""
Geospatial + advanced analytics endpoints (cached).

* GET /geo       — per-community centroid + price/sqft + gross yield + volume,
                   for the interactive map/heatmap.
* GET /analytics — extra chart series: price distribution, base-rate↔price
                   scatter, yield↔price scatter, seasonality, price by type.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.tools.cache import cached_json
from app.tools.duckdb_engine import get_engine

router = APIRouter(tags=["analytics"])


def _geo() -> list[dict]:
    e = get_engine()
    return e.run_query(
        """
        WITH geo AS (
          SELECT community, MAX(zone) AS zone, AVG(lat) AS lat, AVG(lon) AS lon,
                 AVG(price_per_sqft_usd) FILTER (WHERE transaction_type='secondary') AS ppsf,
                 COUNT(*) FILTER (WHERE transaction_type='secondary') AS n,
                 AVG(to_burj_khalifa_km) AS dist
          FROM transactions GROUP BY community),
        y AS (SELECT community, AVG(rental_yield_pct) AS yld FROM area_monthly WHERE year=2025 GROUP BY community)
        SELECT g.community, g.zone, ROUND(g.lat,5) AS lat, ROUND(g.lon,5) AS lon,
               ROUND(g.ppsf) AS price_per_sqft, g.n AS n_secondary,
               ROUND(y.yld,2) AS yield_pct, ROUND(g.dist,1) AS dist_km
        FROM geo g LEFT JOIN y USING(community)
        WHERE g.lat IS NOT NULL
        ORDER BY price_per_sqft DESC
        """
    ).rows


def _analytics() -> dict:
    e = get_engine()

    def q(sql: str) -> list[dict]:
        return e.run_query(sql).rows

    return {
        "price_distribution": q(
            "SELECT CAST(price_per_sqft_usd/100 AS INT)*100 AS bin, COUNT(*) AS n "
            "FROM transactions WHERE transaction_type='secondary' AND price_per_sqft_usd < 2600 "
            "GROUP BY bin ORDER BY bin"
        ),
        "rate_vs_price": q(
            "SELECT year_month, ROUND(AVG(cbuae_base_rate_pct),2) AS base_rate, "
            "ROUND(AVG(secondary_price_per_sqft_usd)) AS price_per_sqft "
            "FROM area_monthly GROUP BY year_month ORDER BY year_month"
        ),
        "yield_vs_price": q(
            "SELECT community, ROUND(AVG(secondary_price_per_sqft_usd)) AS price_per_sqft, "
            "ROUND(AVG(rental_yield_pct),2) AS yield_pct "
            "FROM area_monthly WHERE year=2025 GROUP BY community HAVING price_per_sqft IS NOT NULL"
        ),
        "seasonality": q(
            "SELECT month, ROUND(AVG(secondary_ppsf_mom_pct),2) AS avg_mom_pct "
            "FROM area_monthly WHERE secondary_ppsf_mom_pct IS NOT NULL GROUP BY month ORDER BY month"
        ),
        "price_by_type": q(
            "SELECT property_type, ROUND(AVG(price_per_sqft_usd)) AS price_per_sqft, COUNT(*) AS n "
            "FROM transactions WHERE transaction_type='secondary' GROUP BY property_type ORDER BY price_per_sqft DESC"
        ),
    }


@router.get("/geo")
async def geo() -> list[dict]:
    return await cached_json("dpa:geo", _geo)


@router.get("/analytics")
async def analytics() -> dict:
    return await cached_json("dpa:analytics", _analytics)
