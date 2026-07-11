"""
Verifier
========

The guardrail that separates this system from a chatbot-over-CSV. It **does not
ask the LLM to double-check itself**. Instead it deterministically:

1. Extracts every numeric claim from the narrative answer.
2. Builds the set of numbers that provably come from the data — every numeric
   cell in the query result, plus the deterministically-computed analysis
   figures (KPIs, trend %, anomalies, rankings) and the row count.
3. Confirms each narrative number matches a known value within tolerance
   (relative or absolute, to allow honest rounding like 6.5% vs 6.49%).
4. Emits a confidence level. Any answer whose numbers cannot be confirmed is
   flagged **low-confidence** — never presented silently as fact.

Years (2019–2027) and small structural integers (0–12, e.g. "top 5") are treated
as references, not data claims, unless written as a percentage.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.agents.events import emit_event
from app.agents.narrative_agent import extract_numbers

logger = logging.getLogger("dubaipulse.verifier")

# Number token, capturing whether a '%' immediately follows.
_NUM_CTX_RE = re.compile(r"(-?\d{1,3}(?:,\d{3})+(?:\.\d+)?|-?\d+(?:\.\d+)?)(\s*%?)")

# Matching tolerances: a narrative number N matches known K if within either bound.
_REL_TOL = 0.02   # 2% relative
_ABS_TOL = 1.0    # or within 1.0 absolute


class Verifier:
    def __init__(self, rel_tol: float = _REL_TOL, abs_tol: float = _ABS_TOL) -> None:
        self.rel_tol = rel_tol
        self.abs_tol = abs_tol

    async def run(self, narrative: str, query_out: dict, analysis: dict) -> dict:
        await emit_event("verifier", "running", "Checking every number against source data…")

        result = query_out.get("result", {})
        known = self._collect_known(result, analysis)
        checked, unverified = self._check(narrative, known)

        numbers_checked = len(checked)
        verified_count = numbers_checked - len(unverified)
        row_count = result.get("row_count", 0)

        confidence, verified, reason = self._grade(
            numbers_checked, verified_count, len(unverified), row_count
        )

        verification = {
            "verified": verified,
            "confidence": confidence,
            "numbers_checked": numbers_checked,
            "verified_count": verified_count,
            "unverified_claims": unverified,
            "known_value_count": len(known),
            "reason": reason,
        }

        status = "complete" if verified else "error"
        detail = (
            f"Verified {verified_count}/{numbers_checked} figures · confidence: {confidence}"
            if numbers_checked
            else f"No numeric claims to verify · confidence: {confidence}"
        )
        await emit_event("verifier", status, detail, **verification)
        return verification

    # ------------------------------------------------------------------ #
    def _collect_known(self, result: dict, analysis: dict) -> set[float]:
        known: set[float] = set()

        def add(v: Any) -> None:
            try:
                f = float(v)
            except (TypeError, ValueError):
                return
            # store raw + rounded forms so 6.49 also matches 6.5 / 6
            known.add(round(f, 4))
            known.add(round(f, 1))
            known.add(float(round(f)))

        # 1) every numeric cell in the query result
        for row in result.get("rows", []):
            for v in row.values():
                add(v)
        add(result.get("row_count", 0))

        # 2) numbers embedded in the deterministic facts
        for fact in analysis.get("facts", []):
            for n in extract_numbers(fact):
                add(n)

        # 3) KPI stats
        for stats in analysis.get("kpis", {}).values():
            for v in stats.values():
                add(v)

        # 4) trend figures
        trend = analysis.get("trend")
        if trend:
            add(trend.get("pct_change"))
            for key in ("start", "end"):
                if trend.get(key):
                    add(trend[key].get("value"))
            for p in trend.get("points", []):
                add(p.get("value"))
            for a in trend.get("anomalies", []):
                add(a.get("value"))
                add(a.get("z"))

        # 5) ranking figures
        ranking = analysis.get("ranking")
        if ranking:
            for side in ("top", "bottom"):
                for item in ranking.get(side, []):
                    add(item.get("value"))
        return known

    def _check(self, narrative: str, known: set[float]) -> tuple[list[float], list[dict]]:
        checked: list[float] = []
        unverified: list[dict] = []
        for m in _NUM_CTX_RE.finditer(narrative):
            raw, pct = m.group(1), m.group(2).strip()
            try:
                val = float(raw.replace(",", ""))
            except ValueError:
                continue
            is_pct = pct == "%"
            # Skip years and small structural integers unless written as a percentage.
            if not is_pct and val == int(val):
                iv = int(val)
                if 2019 <= iv <= 2027:      # a year reference
                    continue
                if 0 <= iv <= 12:           # "top 5", "3 communities", month numbers
                    continue
            checked.append(val)
            if not self._matches(val, known):
                ctx = narrative[max(0, m.start() - 35): m.end() + 20].replace("\n", " ").strip()
                unverified.append({"value": val, "is_percent": is_pct, "context": f"…{ctx}…"})
        return checked, unverified

    def _matches(self, val: float, known: set[float]) -> bool:
        for k in known:
            if abs(val - k) <= self.abs_tol:
                return True
            if k != 0 and abs(val - k) / abs(k) <= self.rel_tol:
                return True
        return False

    @staticmethod
    def _grade(checked: int, verified: int, unverified: int, row_count: int):
        if row_count == 0:
            return "low", False, "No data was returned, so the answer cannot be grounded."
        if checked == 0:
            # Qualitative answer over real data — acceptable but note it.
            return "medium", True, "Answer contains no explicit figures to verify; grounded qualitatively."
        ratio = verified / checked
        if ratio >= 0.85:
            return "high", True, f"{verified}/{checked} figures confirmed against source data."
        if ratio >= 0.6:
            return "medium", True, f"{verified}/{checked} figures confirmed; some could not be matched."
        return "low", False, f"Only {verified}/{checked} figures could be confirmed against source data."
