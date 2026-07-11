"""
Narrative Agent
===============

Turns the structured Query + Analysis output into a clear, executive-style
answer that **cites the data it used** (row count, date range, filters, tables).

Grounding contract: the model is instructed to use ONLY the numbers present in
the provided FACTS / DATA. The Verifier then independently checks that every
number in the answer traces back to the queried data — so this instruction is
enforced, not merely requested.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app import telemetry
from app.agents.events import emit_event
from app.tools.llm import LLMProtocol, stream_or_complete

logger = logging.getLogger("dubaipulse.narrative_agent")

_TIME_COLS = ["month_date", "year_month", "quarter", "date_listed", "year"]

_SYSTEM = """You are a Dubai real-estate market analyst writing for a busy executive.
Write a clear, concise answer (120–220 words) to the user's question.

STRICT GROUNDING RULES:
- Use ONLY numbers that appear in the FACTS or DATA blocks provided. Never invent or
  recompute figures. If a figure isn't provided, describe the pattern qualitatively.
- Lead with the direct answer, then the key supporting numbers, then a one-line "why/context".
- If CAVEATS are provided, weave them in honestly (e.g. gross yields, correlation not causation).
- Use USD and Dubai place names exactly as given. Format large numbers with thousands separators.
- Markdown allowed (bold, short lists). No headings. Do not mention SQL or that you are an AI.
"""


class NarrativeAgent:
    def __init__(self, llm: LLMProtocol) -> None:
        self.llm = llm

    async def run(self, question: str, query_out: dict, analysis: dict,
                  language: str = "en", history: list | None = None) -> dict:
        await emit_event("narrative_agent", "running", "Composing the executive answer…")

        result = query_out.get("result", {})
        facts = analysis.get("facts", [])
        notes = analysis.get("notes", [])
        citations = self._citations(query_out, result)

        system = self._system_for(language)
        user = self._build_prompt(
            question, facts, result, notes, query_out.get("filters_summary", ""), history
        )

        # Stream tokens as they arrive (falls back to a single call for stubs /
        # non-streaming providers). The frontend renders them live.
        narrative = ""
        try:
            async for delta in stream_or_complete(self.llm, system, user):
                narrative += delta
                await emit_event("narrative_agent", "running", "", type="token", delta=delta)
        except Exception as exc:
            logger.warning("Narrative generation failed: %s", exc)
            narrative = self._fallback(facts, citations)
            await emit_event("narrative_agent", "running", "", type="token", delta=narrative)

        narrative = narrative.strip()
        telemetry.record_llm(len(system) + len(user), len(narrative))
        await emit_event(
            "narrative_agent", "complete", "Drafted answer with citations.",
            citations=citations, word_count=len(narrative.split()),
        )
        return {"narrative": narrative, "citations": citations}

    # ------------------------------------------------------------------ #
    @staticmethod
    def _system_for(language: str) -> str:
        if language == "ar":
            return (
                _SYSTEM
                + "\n\nIMPORTANT: Write your ENTIRE answer in Arabic (العربية), in natural fluent"
                " Modern Standard Arabic. Keep place names recognisable and all numbers exact."
            )
        return _SYSTEM

    def _build_prompt(self, question, facts, result, notes, filters_summary, history=None) -> str:
        preview = result.get("rows", [])[:15]
        cols = result.get("columns", [])
        facts_block = "\n".join(f"- {f}" for f in facts) if facts else "- (no derived facts)"
        data_block = self._table_md(cols, preview)
        caveats = "\n".join(f"- {n}" for n in notes) if notes else "- (none)"
        hist_block = ""
        if history:
            turns = [t for t in history if t.get("content")][-4:]
            if turns:
                lines = "\n".join(f"{t.get('role', 'user')}: {t.get('content', '')}" for t in turns)
                hist_block = f"CONVERSATION SO FAR (for context/continuity):\n{lines}\n\n"
        return (
            f"{hist_block}"
            f"QUESTION:\n{question}\n\n"
            f"FILTERS APPLIED: {filters_summary or '(see data)'}\n\n"
            f"FACTS (deterministically computed — safe to cite verbatim):\n{facts_block}\n\n"
            f"DATA (first rows of the query result):\n{data_block}\n\n"
            f"CAVEATS:\n{caveats}\n\n"
            "Write the answer now."
        )

    @staticmethod
    def _table_md(cols: list[str], rows: list[dict]) -> str:
        if not rows:
            return "(no rows)"
        header = " | ".join(cols)
        sep = " | ".join("---" for _ in cols)
        body = "\n".join(" | ".join(str(r.get(c, "")) for c in cols) for r in rows)
        return f"{header}\n{sep}\n{body}"

    def _citations(self, query_out: dict, result: dict) -> dict[str, Any]:
        """Deterministic provenance: row count, date range, filters, tables, SQL."""
        rows = result.get("rows", [])
        date_range = self._date_range(rows)
        return {
            "row_count": result.get("row_count", 0),
            "truncated": result.get("truncated", False),
            "date_range": date_range,
            "filters": query_out.get("filters_summary", ""),
            "tables": query_out.get("tables", []),
            "sql": result.get("sql", ""),
        }

    @staticmethod
    def _date_range(rows: list[dict]) -> dict | None:
        for col in _TIME_COLS:
            vals = [str(r[col]) for r in rows if r.get(col) is not None]
            if vals:
                return {"column": col, "min": min(vals), "max": max(vals)}
        return None

    @staticmethod
    def _fallback(facts: list[str], citations: dict) -> str:
        """Deterministic answer if the LLM is unavailable (keeps the system honest)."""
        if not facts:
            return "The query returned no data for this question, so no answer can be grounded."
        body = " ".join(facts)
        return f"Based on the queried data ({citations.get('row_count', 0)} rows): {body}"


# Number extraction shared with the Verifier lives here so both agents agree
# on what "a number in the answer" means.
_NUMBER_RE = re.compile(r"-?\d{1,3}(?:,\d{3})+(?:\.\d+)?|-?\d+(?:\.\d+)?")


def extract_numbers(text: str) -> list[float]:
    """Extract numeric tokens from prose (handles thousands separators)."""
    out: list[float] = []
    for tok in _NUMBER_RE.findall(text):
        try:
            out.append(float(tok.replace(",", "")))
        except ValueError:
            continue
    return out
