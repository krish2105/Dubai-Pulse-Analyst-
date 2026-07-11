# DubaiPulse Analyst — Data Dictionary

## Source

- **Dataset:** *Dubai Real Estate: Sales, Off-Plan & Rentals (2020–2026)*
- **Author / Kaggle slug:** `sergionefedov/dubai-real-estate-sales-and-rentals-20202026`
- **License:** CC0 1.0 (Public Domain)
- **Coverage:** January 2020 → April 2026, across **84 communities** and **52 zones** in Dubai.
- **Currency:** All monetary values are in **USD** (for international comparability).

The dataset blends **real geographic anchors** (community coordinates, Dubai Metro
stations, the CBUAE base-rate timeline, and DLD / Property Finder–anchored base prices
per zone) with a **hedonic pricing model** that generates listing-level attributes and
prices consistent with those anchors. It reflects real market events: the COVID-19 dip
(2020), the Expo 2020 rally, post-2022 capital inflows, the October 2022 Golden Visa
expansion, and the post-2023 cooling.

---

## ⚠️ Known limitations (stated explicitly — not hidden)

These are surfaced by the agents (as caveats) and must be understood when interpreting answers:

1. **Coordinates are jittered** around community centroids — they are *not* exact addresses.
2. **No micro-location amenity features** beyond metro distance (no school / park / retail proximity).
3. **No service-charge field** — therefore all rental **yields are *gross*** (rent ÷ price),
   not net of service charges, and are systematically higher than realised net yields.
4. **Listing-level attributes are hedonic-model outputs**, calibrated to real base prices —
   they are realistic and internally consistent but are *not* individual recorded DLD transactions.
5. **`floor` / `total_floors` are null for villas** (≈ 18k secondary rows) — expected, not missing data.
6. **Off-plan and rentals start in 2021** (secondary starts in 2020); pre-2021 off-plan/rental
   listing-level data does not exist in the source.

---

## Raw files (`backend/data/raw/`)

| File | Grain | Rows | Description |
|------|-------|------|-------------|
| `secondary_sales.csv` | listing | 50,000 | Ready / resale sales listings |
| `off_plan.csv` | listing | 12,000 | Off-plan (under-construction) sales listings |
| `rentals.csv` | listing | 25,000 | Residential rental listings (annual rent) |
| `area_prices_monthly.csv` | community × month | 6,384 | Monthly aggregate price/volume series + macro rates |
| `metro_stations.csv` | station | 55 | Dubai Metro stations with coordinates |

---

## Processed files (`backend/data/processed/`)

Built deterministically by `app/data_pipeline.py`. These are the tables the agents query via DuckDB.

### 1. `transactions.parquet` — unified listing-level fact table (87,000 rows)

One row per listing across **all three** transaction types, distinguished by `transaction_type`.
**For rentals, `price_usd` holds the annual rent** (and `price_per_sqft_usd` the rent per sqft).

| Column | Type | Grain / Notes |
|--------|------|---------------|
| `id` | str | Source listing id (e.g. `S000001`, `O000001`, `R000001`) |
| `transaction_type` | str | `secondary` \| `offplan` \| `rental` |
| `date_listed` | date | Listing date |
| `year_month` | str | `YYYY-MM` (derived) |
| `year` | int | Calendar year (derived) |
| `quarter` | str | `YYYY-Qn` (derived) |
| `community` | str | One of 84 communities |
| `zone` | str | One of 52 zones (a zone groups communities) |
| `lat`, `lon` | float | Jittered community-centroid coordinates |
| `to_burj_khalifa_km` | float | Straight-line distance to Burj Khalifa |
| `metro_station` | str | Nearest metro station |
| `metro_line` | str | `Red` \| `Green` \| … |
| `metro_distance_min` | float | Minutes to nearest metro |
| `property_category` | str | `apartment` \| `villa` |
| `property_type` | str | `studio`, `1BR`…`3BR`, `3BR_villa`, `4BR_penthouse`, `4BR_villa`, `5BR_villa`, `6BR_villa` |
| `bedrooms` | int | 0 (studio) … 6 |
| `area_sqft`, `area_m2` | float | Unit area |
| `view` | str | `sea`, `marina`, `burj_khalifa`, `golf_course`, `park`, `pool`, `city`, `community` |
| `furnishing` | str? | `unfurnished` \| `semi_furnished` \| `fully_furnished` (null for off-plan) |
| `is_freehold` | bool? | Freehold ownership (null for rentals) |
| `price_usd` | float | Sale price — **or annual rent for rentals** |
| `price_per_sqft_usd` | float | Price (or rent) per sqft |
| `price_per_m2_usd` | float | Price (or rent) per m² |
| `mortgage_rate_at_listing` | float | Prevailing mortgage rate (%) at listing date |
| `condition` | str? | Secondary only: `vacant_on_transfer`, `tenanted`, `off_plan_resale` |
| `floor` | float? | Secondary apartments only (null for villas) |
| `year_built` | int? | Secondary only |
| `parking_spaces` | int? | Secondary / rental |
| `chiller_included` | bool? | Secondary / rental |
| `developer` | str? | Off-plan only (e.g. `Emaar`, `Sobha`, `Nakheel`) |
| `developer_tier` | str? | Off-plan only: `tier1` \| `tier2` |
| `project_name` | str? | Off-plan only |
| `launch_year`, `handover_year` | int? | Off-plan only |
| `payment_plan` | str? | Off-plan only: `70/30`, `60/40`, `80/20`, `50/50_post_handover`, `10/90_post_handover` |
| `contract_type` | str? | Rental only: `yearly` \| `short_term` |
| `n_cheques` | int? | Rental only: number of rent cheques |

### 2. `area_monthly.parquet` — enriched monthly time-series (6,384 rows)

One row per **community × freehold-status × month**. Carries the macro context, so this is the
primary table for **trend / anomaly** questions.

| Column | Type | Notes |
|--------|------|-------|
| `year_month` | str | `YYYY-MM` |
| `month_date` | date | Month-start date (derived, for ordering) |
| `year`, `month` | int | Derived |
| `community`, `zone` | str | |
| `is_freehold` | bool | |
| `secondary_price_per_sqft_usd` | float | Monthly median secondary price/sqft |
| `secondary_price_per_m2_usd` | float | |
| `offplan_price_per_sqft_usd` | float? | Null when no off-plan activity that month |
| `rental_price_per_sqft_annual_usd` | float | Annual rent per sqft |
| `n_listings_secondary` / `_offplan` / `_rental` | int | Monthly listing counts (volume proxy) |
| `cbuae_base_rate_pct` | float | CBUAE base rate that month (real macro anchor) |
| `avg_mortgage_rate_pct` | float | Average mortgage rate that month |
| `rental_yield_pct` | float | **Derived:** gross yield = rent/sqft ÷ price/sqft × 100 |
| `secondary_ppsf_mom_pct` | float | **Derived:** month-over-month % change (per community) |
| `secondary_ppsf_yoy_pct` | float | **Derived:** year-over-year % change (per community) |

### 3. `metro_stations.parquet` — reference (55 rows)

| Column | Type | Notes |
|--------|------|-------|
| `station_name` | str | |
| `line` | str | `Red` \| `Green` |
| `lat`, `lon` | float | Real coordinates |
| `year_opened` | int | |
| `to_burj_khalifa_km` | float | |

---

## Derived-metric definitions (used by the Analysis Agent)

- **Rental yield (gross), %** = `rental_price_per_sqft_annual_usd / secondary_price_per_sqft_usd × 100`.
  Gross only — excludes service charges (not in source).
- **Month-over-month (MoM) price change, %** = period-over-period % change of secondary price/sqft.
- **Year-over-year (YoY) price change, %** = 12-month % change of secondary price/sqft.
- **Transaction volume** = count of listings (`n_listings_*` in the monthly table, or `COUNT(*)` on transactions).
- **Anomaly flag** = a month whose value deviates > 2σ from the trailing rolling mean (rolling z-score),
  computed at query time by the Analysis Agent.
