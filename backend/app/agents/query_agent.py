"""
Query Agent
===========

Translates a natural-language question into a **read-only DuckDB SQL query**,
executes it through the safe engine, and returns structured results.

* The LLM only *proposes* SQL; execution goes through ``DuckDBEngine`` which
  enforces read-only + row caps (see ``tools/duckdb_engine.py``).
* If the generated SQL fails or returns nothing, the agent retries once,
  feeding the error back to the model (self-correction).
* All steps are emitted as trace events.
"""

from __future__ import annotations

import logging

from app.agents.events import emit_event
from app.tools.duckdb_engine import DuckDBEngine, QueryResult, get_engine
from app.tools.llm import LLMProtocol, extract_json

logger = logging.getLogger("dubaipulse.query_agent")

_SYSTEM_TEMPLATE = """You are a meticulous SQL analyst for a Dubai real-estate database.
Given a user question, write ONE read-only DuckDB SQL query that answers it.

{schema}

Rules:
- Output ONLY a JSON object, no prose, with keys:
  {{"sql": "<single SELECT/WITH query>",
    "rationale": "<one sentence: what the query computes>",
    "tables": ["<tables used>"],
    "filters_summary": "<plain-English filters, e.g. 'secondary sales, Palm Jumeirah, 2025'>"}}
- The query MUST be a single read-only SELECT or WITH statement. No semicolons chaining,
  no INSERT/UPDATE/DELETE/DDL.
- Aggregate the data (AVG/MEDIAN/COUNT/…) — do not dump raw listings unless explicitly asked.
- Round monetary aggregates. Add ORDER BY and a sensible LIMIT (<= 50).
- Use exact community/zone spellings from the schema. If a needed value is not in the schema,
  choose the closest valid one and note it in filters_summary.
"""


class QueryAgent:
    def __init__(self, llm: LLMProtocol, engine: DuckDBEngine | None = None) -> None:
        self.llm = llm
        self.engine = engine or get_engine()

    async def run(self, question: str) -> dict:
        """Return {sql, rationale, filters_summary, tables, result: QueryResult.to_dict()}."""
        await emit_event("query_agent", "running", "Translating question into SQL…")

        system = _SYSTEM_TEMPLATE.format(schema=self.engine.get_schema_prompt())
        proposal = await self._propose(system, question)
        sql = proposal.get("sql", "")
        result = self.engine.run_query(sql)

        # ---- self-correction: one retry if the query failed or was empty ---- #
        if result.error or result.row_count == 0:
            reason = result.error or "the query returned zero rows"
            await emit_event(
                "query_agent", "running",
                f"First query {('failed' if result.error else 'was empty')}; retrying…",
                error=reason,
            )
            retry_user = (
                f"Original question: {question}\n\n"
                f"Your previous SQL was:\n{sql}\n\n"
                f"It did not work because: {reason}.\n"
                "Fix the query. Re-check table/column names and value spellings. "
                "Return the same JSON format."
            )
            proposal = await self._propose(system, retry_user)
            sql = proposal.get("sql", sql)
            result = self.engine.run_query(sql)

        status = "error" if result.error else "complete"
        detail = (
            f"Query failed: {result.error}"
            if result.error
            else f"Executed SQL · {result.row_count} row(s) returned"
        )
        await emit_event(
            "query_agent", status, detail,
            sql=result.sql, row_count=result.row_count,
            filters_summary=proposal.get("filters_summary", ""),
            rationale=proposal.get("rationale", ""),
            columns=result.columns,
            preview=result.rows[:5],
        )

        return {
            "sql": result.sql,
            "rationale": proposal.get("rationale", ""),
            "filters_summary": proposal.get("filters_summary", ""),
            "tables": proposal.get("tables", []),
            "result": result.to_dict(),
        }

    async def _propose(self, system: str, user: str) -> dict:
        """Ask the LLM for a SQL proposal (JSON). Falls back gracefully."""
        try:
            raw = await self.llm.complete(
                system=system, user=user, model=self.engine.settings.anthropic_sql_model
            )
            data = extract_json(raw)
            if "sql" not in data:
                data["sql"] = ""
            return data
        except Exception as exc:  # LLMError / JSON error
            logger.warning("Query proposal failed: %s", exc)
            return {"sql": "", "rationale": "", "filters_summary": "", "tables": [], "_error": str(exc)}

    # Convenience for callers that just want the QueryResult object.
    @staticmethod
    def result_from_dict(d: dict) -> QueryResult:
        r = d["result"]
        return QueryResult(
            sql=r["sql"], columns=r["columns"], rows=r["rows"],
            row_count=r["row_count"], truncated=r["truncated"], error=r["error"], meta=r["meta"],
        )
