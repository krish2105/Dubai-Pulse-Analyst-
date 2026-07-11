"""
DubaiPulse Analyst — Data Pipeline
==================================

Transforms the *real* Kaggle dataset
("Dubai Real Estate: Sales, Off-Plan & Rentals 2020-2026",
 sergionefedov/dubai-real-estate-sales-and-rentals-20202026, CC0)
from ``backend/data/raw/`` into clean, analysis-ready Parquet files in
``backend/data/processed/`` that the DuckDB query layer consumes.

Outputs
-------
1. ``transactions.parquet`` — a UNIFIED listing-level fact table combining
   secondary sales, off-plan and rentals into one schema, distinguished by a
   ``transaction_type`` column. This is what the Query Agent hits for
   distributional / comparison questions (price per sqft by zone, yields,
   volumes, etc.). For rentals, ``price_usd`` holds the *annual rent*.

2. ``area_monthly.parquet`` — the cleaned monthly aggregate time-series
   (one row per community × month), enriched with deterministic derived
   columns (month-over-month %, year-over-year %, rental yield, macro rates).
   This is what the Analysis Agent hits for trend / anomaly questions because
   it carries the macro context (CBUAE base rate, mortgage rate).

3. ``metro_stations.parquet`` — reference table of Dubai Metro stations.

The pipeline is deterministic and idempotent: run it as many times as you like
and you get byte-stable outputs. Run with::

    python -m app.data_pipeline          # from the backend/ directory

Design notes
------------
* We never fabricate rows. Every processed row traces back to a raw row.
* Cleaning is conservative: we fix dtypes, standardise column names, derive
  a handful of unambiguous fields, and flag (not drop) macro context.
* The *known limitations* of the source (jittered coordinates, no service
  charge, hedonic-model listing attributes) are documented in
  ``backend/data/data_dictionary.md`` and surfaced by the agents, not hidden.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger("dubaipulse.pipeline")

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
# This file lives at backend/app/data_pipeline.py, so:
#   parents[0] = app/, parents[1] = backend/
BACKEND_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = BACKEND_DIR / "data" / "raw"
PROCESSED_DIR = BACKEND_DIR / "data" / "processed"

# --------------------------------------------------------------------------- #
# Column schema for the unified `transactions` table.
# Keeping this explicit (rather than an implicit union) makes the output schema
# stable and self-documenting for the NL->SQL agent.
# --------------------------------------------------------------------------- #
UNIFIED_COLUMNS = [
    # identity / classification
    "id",
    "transaction_type",       # 'secondary' | 'offplan' | 'rental'
    "date_listed",            # DATE
    "year_month",             # 'YYYY-MM'
    "year",                   # INT
    "quarter",                # 'YYYY-Qn'
    # location
    "community",
    "zone",
    "lat",
    "lon",
    "to_burj_khalifa_km",
    "metro_station",
    "metro_line",
    "metro_distance_min",
    # property attributes
    "property_category",      # 'apartment' | 'villa'
    "property_type",          # e.g. '1BR', '3BR_villa', 'studio'
    "bedrooms",
    "area_sqft",
    "area_m2",
    "view",
    "furnishing",             # nullable (offplan has none)
    "is_freehold",            # nullable (rentals have none)
    # money (for rentals: annual rent)
    "price_usd",
    "price_per_sqft_usd",
    "price_per_m2_usd",
    "mortgage_rate_at_listing",
    # type-specific extras (nullable)
    "condition",              # secondary only
    "floor",                  # secondary only
    "year_built",             # secondary only
    "parking_spaces",         # secondary/rental
    "chiller_included",       # secondary/rental
    "developer",              # offplan only
    "developer_tier",         # offplan only
    "project_name",           # offplan only
    "launch_year",            # offplan only
    "handover_year",          # offplan only
    "payment_plan",           # offplan only
    "contract_type",          # rental only
    "n_cheques",              # rental only
]


def _read_csv(name: str) -> pd.DataFrame:
    path = RAW_DIR / name
    if not path.exists():
        raise FileNotFoundError(
            f"Missing raw file: {path}\n"
            "Place the Kaggle dataset CSVs in backend/data/raw/ before running "
            "the pipeline. See backend/data/data_dictionary.md for the source."
        )
    return pd.read_csv(path)


def _add_time_cols(df: pd.DataFrame, date_col: str = "date_listed") -> pd.DataFrame:
    """Derive deterministic time columns from a listing date."""
    dt = pd.to_datetime(df[date_col], errors="coerce")
    df[date_col] = dt.dt.date
    df["year_month"] = dt.dt.strftime("%Y-%m")
    df["year"] = dt.dt.year.astype("Int64")
    df["quarter"] = dt.dt.year.astype("Int64").astype(str) + "-Q" + dt.dt.quarter.astype("Int64").astype(str)
    return df


def build_transactions() -> pd.DataFrame:
    """Combine the three listing-level tables into one unified fact table."""
    logger.info("Building unified transactions table...")

    # ---- Secondary sales -------------------------------------------------- #
    sec = _read_csv("secondary_sales.csv")
    sec = _add_time_cols(sec)
    sec["transaction_type"] = "secondary"
    sec = sec.rename(columns={})  # names already align; kept for clarity

    # ---- Off-plan --------------------------------------------------------- #
    off = _read_csv("off_plan.csv")
    off = _add_time_cols(off)
    off["transaction_type"] = "offplan"

    # ---- Rentals ---------------------------------------------------------- #
    rent = _read_csv("rentals.csv")
    rent = _add_time_cols(rent)
    rent["transaction_type"] = "rental"
    # For rentals the "price" is the annual rent — map it onto the shared cols
    # so cross-type queries stay simple and honest (documented in data dict).
    rent = rent.rename(
        columns={
            "annual_rent_usd": "price_usd",
            "rent_per_sqft_usd": "price_per_sqft_usd",
            "rent_per_m2_usd": "price_per_m2_usd",
        }
    )

    # Ensure every unified column exists in each frame (fill missing w/ NA)
    frames = []
    for frame in (sec, off, rent):
        for col in UNIFIED_COLUMNS:
            if col not in frame.columns:
                frame[col] = pd.NA
        frames.append(frame[UNIFIED_COLUMNS])

    unified = pd.concat(frames, ignore_index=True)

    # ---- Type coercion for a clean, queryable schema ---------------------- #
    unified["bedrooms"] = pd.to_numeric(unified["bedrooms"], errors="coerce").astype("Int64")
    unified["year"] = pd.to_numeric(unified["year"], errors="coerce").astype("Int64")
    for col in ("area_sqft", "area_m2", "price_usd", "price_per_sqft_usd",
                "price_per_m2_usd", "to_burj_khalifa_km", "lat", "lon",
                "metro_distance_min", "mortgage_rate_at_listing"):
        unified[col] = pd.to_numeric(unified[col], errors="coerce")

    # Normalise boolean-ish fields to nullable booleans
    for col in ("is_freehold", "chiller_included"):
        unified[col] = unified[col].map(
            {True: True, False: False, "True": True, "False": False}
        ).astype("boolean")

    logger.info("Unified transactions rows: %d", len(unified))
    return unified


def build_area_monthly() -> pd.DataFrame:
    """Clean + enrich the monthly community aggregate time-series."""
    logger.info("Building area_monthly table...")
    area = _read_csv("area_prices_monthly.csv")

    # Parse the year_month into a real month-start date for time ordering.
    area["month_date"] = pd.to_datetime(area["year_month"], format="%Y-%m", errors="coerce")
    area["year"] = area["month_date"].dt.year.astype("Int64")
    area["month"] = area["month_date"].dt.month.astype("Int64")

    # Rental (gross) yield: annual rent per sqft / sale price per sqft.
    # Both are community-month medians in the source, so the ratio is a clean,
    # honest gross-yield estimate (excludes service charges — see data dict).
    area["rental_yield_pct"] = (
        area["rental_price_per_sqft_annual_usd"] / area["secondary_price_per_sqft_usd"] * 100
    ).round(2)

    # Deterministic month-over-month and year-over-year price changes,
    # computed per community for the secondary price/sqft series.
    area = area.sort_values(["community", "is_freehold", "month_date"]).reset_index(drop=True)
    grp = area.groupby(["community", "is_freehold"], dropna=False)["secondary_price_per_sqft_usd"]
    area["secondary_ppsf_mom_pct"] = (grp.pct_change(1) * 100).round(2)
    area["secondary_ppsf_yoy_pct"] = (grp.pct_change(12) * 100).round(2)

    logger.info("area_monthly rows: %d", len(area))
    return area


def build_metro() -> pd.DataFrame:
    logger.info("Building metro_stations table...")
    return _read_csv("metro_stations.csv")


def run() -> dict[str, Path]:
    """Execute the full pipeline and write Parquet outputs. Returns paths."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    transactions = build_transactions()
    area_monthly = build_area_monthly()
    metro = build_metro()

    outputs = {
        "transactions": PROCESSED_DIR / "transactions.parquet",
        "area_monthly": PROCESSED_DIR / "area_monthly.parquet",
        "metro_stations": PROCESSED_DIR / "metro_stations.parquet",
    }
    transactions.to_parquet(outputs["transactions"], index=False)
    area_monthly.to_parquet(outputs["area_monthly"], index=False)
    metro.to_parquet(outputs["metro_stations"], index=False)

    logger.info("Wrote processed files:")
    for name, path in outputs.items():
        size_kb = path.stat().st_size / 1024
        logger.info("  %-16s %8.1f KB  %s", name, size_kb, path)

    # Emit a tiny manifest for quick sanity checks / debugging.
    manifest = PROCESSED_DIR / "_manifest.txt"
    manifest.write_text(
        "\n".join(
            [
                f"transactions rows: {len(transactions)}",
                f"area_monthly rows: {len(area_monthly)}",
                f"metro_stations rows: {len(metro)}",
                f"transactions columns: {', '.join(transactions.columns)}",
            ]
        )
        + "\n"
    )
    return outputs


if __name__ == "__main__":
    run()
