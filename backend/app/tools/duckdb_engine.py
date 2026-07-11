"""
DuckDB query engine — the single, safe gateway to the processed data.

Responsibilities
----------------
* Load the processed Parquet files as DuckDB views once, at process start.
* Expose a compact, LLM-friendly **schema description** (columns + real sample
  values + canned examples) for the NL->SQL step.
* Execute **only** read-only ``SELECT`` / ``WITH`` statements, with a hard row
  cap, and return structured results (columns, rows, row_count) that downstream
  agents — crucially the Verifier — can inspect against the narrative.

Security model
--------------
The LLM proposes SQL, but SQL never runs blindly:
* We parse the statement and reject anything that is not a single read-only
  SELECT/WITH (no INSERT/UPDATE/DELETE/CREATE/ATTACH/COPY/PRAGMA/etc.).
* We reject multiple statements (no ``;`` chaining).
* We run inside a DuckDB connection that has no file-system write surface
  beyond the read-only parquet views, and we always enforce a LIMIT.
This is a deterministic guardrail — not "ask the model to behave".
"""

from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import duckdb

from app.config import get_settings

logger = logging.getLogger("dubaipulse.duckdb")

# Statements we allow to *start* with. Anything else is rejected outright.
_ALLOWED_PREFIXES = ("select", "with")

# Keywords that must never appear (defence in depth on top of prefix check).
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|create|alter|attach|detach|copy|pragma|"
    r"export|import|install|load|set|call|vacuum|reindex|truncate|replace)\b",
    re.IGNORECASE,
)


class QueryError(Exception):
    """Raised when a generated query is unsafe or fails to execute."""


@dataclass
class QueryResult:
    """Structured, JSON-serialisable result of a query."""

    sql: str
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    truncated: bool = False
    error: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sql": self.sql,
            "columns": self.columns,
            "rows": self.rows,
            "row_count": self.row_count,
            "truncated": self.truncated,
            "error": self.error,
            "meta": self.meta,
        }


class DuckDBEngine:
    """Thread-safe singleton wrapper around a DuckDB in-memory connection."""

    _instance: DuckDBEngine | None = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self.settings = get_settings()
        self.processed_dir: Path = self.settings.processed_dir
        self._con_lock = threading.Lock()
        self._con = duckdb.connect(database=":memory:")
        self._register_views()
        self._schema_cache: str | None = None

    # ---- singleton accessor ---- #
    @classmethod
    def instance(cls) -> DuckDBEngine:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ---- setup ---- #
    def _register_views(self) -> None:
        files = {
            "transactions": self.processed_dir / "transactions.parquet",
            "area_monthly": self.processed_dir / "area_monthly.parquet",
            "metro_stations": self.processed_dir / "metro_stations.parquet",
        }
        for name, path in files.items():
            if not path.exists():
                raise FileNotFoundError(
                    f"Processed file missing: {path}. "
                    "Run `python -m app.data_pipeline` first."
                )
            # read_parquet keeps the data on disk; the view is a thin pointer.
            self._con.execute(
                f"CREATE OR REPLACE VIEW {name} AS "
                f"SELECT * FROM read_parquet('{path.as_posix()}')"
            )
        logger.info("Registered DuckDB views: %s", ", ".join(files))

    # ---- safety ---- #
    @staticmethod
    def validate_sql(sql: str) -> str:
        """Return cleaned SQL or raise QueryError. Read-only, single statement."""
        if not sql or not sql.strip():
            raise QueryError("Empty SQL.")
        cleaned = sql.strip().rstrip(";").strip()

        # Reject multiple statements (no chaining).
        if ";" in cleaned:
            raise QueryError("Multiple SQL statements are not allowed.")

        lowered = cleaned.lower()
        if not lowered.startswith(_ALLOWED_PREFIXES):
            raise QueryError("Only read-only SELECT/WITH queries are allowed.")

        if _FORBIDDEN.search(cleaned):
            raise QueryError("Query contains a forbidden (non-read-only) keyword.")

        return cleaned

    def _ensure_limit(self, sql: str) -> str:
        """Wrap the query so a hard row cap is always enforced."""
        cap = self.settings.max_result_rows
        # Subquery-wrap so we never fight the user's own LIMIT/ORDER BY.
        return f"SELECT * FROM (\n{sql}\n) AS _q LIMIT {cap + 1}"

    # ---- execution ---- #
    def run_query(self, sql: str) -> QueryResult:
        """Validate + execute a read-only query. Never raises for *query* errors;
        returns a QueryResult with ``error`` set instead (so agents can react)."""
        try:
            cleaned = self.validate_sql(sql)
        except QueryError as exc:
            return QueryResult(sql=sql, columns=[], rows=[], row_count=0, error=str(exc))

        wrapped = self._ensure_limit(cleaned)
        cap = self.settings.max_result_rows
        try:
            with self._con_lock:
                cur = self._con.execute(wrapped)
                columns = [d[0] for d in cur.description]
                fetched = cur.fetchall()
        except Exception as exc:  # duckdb.Error and friends
            return QueryResult(
                sql=cleaned, columns=[], rows=[], row_count=0,
                error=f"SQL execution failed: {exc}",
            )

        truncated = len(fetched) > cap
        fetched = fetched[:cap]
        rows = [self._row_to_jsonable(columns, r) for r in fetched]
        return QueryResult(
            sql=cleaned,
            columns=columns,
            rows=rows,
            row_count=len(rows),
            truncated=truncated,
        )

    @staticmethod
    def _row_to_jsonable(columns: list[str], row: tuple) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for col, val in zip(columns, row, strict=False):
            # DuckDB may return Decimal / date / etc. — coerce to JSON-safe types.
            if hasattr(val, "isoformat"):
                out[col] = val.isoformat()
            elif isinstance(val, bytes | bytearray):
                out[col] = val.decode("utf-8", "replace")
            elif val is not None and val.__class__.__name__ == "Decimal":
                out[col] = float(val)
            else:
                out[col] = val
        return out

    # ---- introspection for the LLM ---- #
    def get_distinct_sample(self, table: str, column: str, limit: int = 60) -> list[Any]:
        try:
            res = self.run_query(
                f"SELECT DISTINCT {column} FROM {table} "
                f"WHERE {column} IS NOT NULL ORDER BY {column} LIMIT {limit}"
            )
            return [r[column] for r in res.rows]
        except Exception:
            return []

    def get_schema_prompt(self) -> str:
        """A compact, real-value-anchored schema block for the NL->SQL prompt."""
        if self._schema_cache is not None:
            return self._schema_cache

        zones = self.get_distinct_sample("transactions", "zone")
        communities = self.get_distinct_sample("transactions", "community")
        ptypes = self.get_distinct_sample("transactions", "property_type")

        date_range = self.run_query(
            "SELECT min(date_listed) AS min_d, max(date_listed) AS max_d FROM transactions"
        ).rows
        drange = date_range[0] if date_range else {"min_d": "?", "max_d": "?"}

        schema = f"""
You are querying a DuckDB database of Dubai real-estate data (Jan 2020 – Apr 2026, USD).
There are exactly three tables. Use ONLY these tables and columns.

────────────────────────────────────────────────────────────────────────
TABLE 1: transactions  — unified listing-level fact table (87,000 rows)
One row per listing. transaction_type ∈ ('secondary','offplan','rental').
IMPORTANT: for rentals, price_usd is the ANNUAL RENT (and price_per_sqft_usd is rent/sqft).
Columns:
  id, transaction_type, date_listed (DATE), year_month ('YYYY-MM'), year (INT), quarter ('YYYY-Qn'),
  community, zone, lat, lon, to_burj_khalifa_km, metro_station, metro_line, metro_distance_min,
  property_category ('apartment'|'villa'), property_type, bedrooms (INT 0-6),
  area_sqft, area_m2, view, furnishing, is_freehold (BOOL, null for rentals),
  price_usd, price_per_sqft_usd, price_per_m2_usd, mortgage_rate_at_listing,
  condition, floor, year_built, parking_spaces, chiller_included,
  developer, developer_tier, project_name, launch_year, handover_year, payment_plan,
  contract_type, n_cheques

TABLE 2: area_monthly  — monthly aggregate time-series (community × freehold × month)
Best for TREND / MACRO questions. Columns:
  year_month, month_date (DATE), year (INT), month (INT), community, zone, is_freehold (BOOL),
  secondary_price_per_sqft_usd, secondary_price_per_m2_usd, offplan_price_per_sqft_usd,
  rental_price_per_sqft_annual_usd, n_listings_secondary, n_listings_offplan, n_listings_rental,
  cbuae_base_rate_pct, avg_mortgage_rate_pct,
  rental_yield_pct  (= rent/sqft ÷ price/sqft × 100, GROSS),
  secondary_ppsf_mom_pct, secondary_ppsf_yoy_pct

TABLE 3: metro_stations — reference. Columns: station_name, line, lat, lon, year_opened, to_burj_khalifa_km
────────────────────────────────────────────────────────────────────────

Real values you can filter on:
  date range: {drange.get('min_d')} → {drange.get('max_d')}
  zones (52): {', '.join(map(str, zones))}
  property_type: {', '.join(map(str, ptypes))}
  communities (sample): {', '.join(map(str, communities[:40]))} ...

Guidance:
  • For "price growth / trend / over time / YoY / MoM" use area_monthly.
  • For "rental yield" use area_monthly.rental_yield_pct.
  • For distributions / per-listing filters (bedrooms, view, developer) use transactions.
  • Community names are precise (e.g. 'Downtown Dubai', 'Dubai Marina', 'Palm Jumeirah').
  • Always aggregate (AVG/MEDIAN/COUNT) rather than returning raw listings unless asked.
  • Prefer ROUND(...) on monetary aggregates. Add ORDER BY + a sensible LIMIT.
"""
        self._schema_cache = schema.strip()
        return self._schema_cache


def get_engine() -> DuckDBEngine:
    return DuckDBEngine.instance()
