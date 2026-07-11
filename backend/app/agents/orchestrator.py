"""
Orchestrator (LangGraph)
========================

Models the full multi-agent flow as an explicit state machine:

    START
      → query_agent        (NL → SQL → data)
      → route              (decide: simple lookup vs analytical)
          ├─ simple    → narrative
          └─ analytical→ analysis → narrative
      → verify
          ├─ low-confidence & retries left → narrative (retry, stricter)
          └─ otherwise                     → finalize → END

Design choices worth defending in an interview:
* Routing is deterministic (keyword + result-shape heuristics) so it is testable
  and predictable — the Analysis Agent is skipped for simple lookups to save
  latency/tokens.
* The retry edge exists specifically to give the Verifier teeth: a low-confidence
  answer is regenerated once with corrective feedback before we ever surface it.
* The event emitter is context-local, so the graph STATE stays clean and
  serialisable (no callbacks threaded through channels).
"""

from __future__ import annotations

import logging
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app import telemetry
from app.agents.analysis_agent import AnalysisAgent
from app.agents.events import AgentEventStream, emit_event, use_emitter
from app.agents.guardrail import InputGuardrail
from app.agents.narrative_agent import NarrativeAgent
from app.agents.query_agent import QueryAgent
from app.agents.verifier import Verifier
from app.tools.llm import LLMClient, LLMProtocol

logger = logging.getLogger("dubaipulse.orchestrator")

MAX_RETRIES = 1

# Words that imply trend / comparison / causation → invoke the Analysis Agent.
_ANALYTICAL_TRIGGERS = (
    "trend", "over time", "grow", "growth", "increase", "decrease", "decline",
    "change", "compare", "comparison", "versus", " vs", "highest", "lowest",
    "rank", "top ", "biggest", "why", "cause", "driver", "spike", "drop",
    "anomaly", "yield", "year-over-year", "yoy", "month-over-month", "mom",
    "between", "from 20", "correlat", "relationship",
)


class OrchestratorState(TypedDict, total=False):
    question: str
    route: str                # 'simple' | 'analytical'
    query_out: dict[str, Any]
    analysis: dict[str, Any]
    narrative: str
    citations: dict[str, Any]
    verification: dict[str, Any]
    retries: int
    verifier_feedback: str
    should_retry: bool
    history: list[dict[str, Any]]
    language: str
    blocked: bool
    block_message: str
    block_category: str
    final: dict[str, Any]


class Orchestrator:
    def __init__(self, llm: LLMProtocol | None = None) -> None:
        self.llm = llm or LLMClient()
        self.guardrail = InputGuardrail()
        self.query_agent = QueryAgent(self.llm)
        self.analysis_agent = AnalysisAgent()
        self.narrative_agent = NarrativeAgent(self.llm)
        self.verifier = Verifier()
        self.graph = self._build_graph()

    # ------------------------------------------------------------------ #
    def _build_graph(self):
        g = StateGraph(OrchestratorState)
        # Node names deliberately differ from state keys (LangGraph forbids collisions).
        g.add_node("guard", self._guard_node)
        g.add_node("refuse", self._refuse_node)
        g.add_node("query", self._query_node)
        g.add_node("planner", self._route_node)
        g.add_node("analyze", self._analysis_node)
        g.add_node("compose", self._narrative_node)
        g.add_node("verify", self._verify_node)
        g.add_node("finalize", self._finalize_node)

        g.add_edge(START, "guard")
        g.add_conditional_edges(
            "guard", self._guard_selector, {"blocked": "refuse", "ok": "query"}
        )
        g.add_edge("refuse", END)
        g.add_edge("query", "planner")
        g.add_conditional_edges(
            "planner", self._route_selector,
            {"analysis": "analyze", "narrative": "compose"},
        )
        g.add_edge("analyze", "compose")
        g.add_edge("compose", "verify")
        g.add_conditional_edges(
            "verify", self._verify_selector,
            {"retry": "compose", "finalize": "finalize"},
        )
        g.add_edge("finalize", END)
        return g.compile()

    # ------------------------------ nodes ----------------------------- #
    async def _guard_node(self, state: OrchestratorState) -> dict:
        from app.config import get_settings
        if not get_settings().guardrail_enabled:
            return {"blocked": False}
        verdict = await self.guardrail.run(state["question"])
        return {
            "blocked": not verdict.allowed,
            "block_message": verdict.message,
            "block_category": verdict.category,
        }

    async def _refuse_node(self, state: OrchestratorState) -> dict:
        message = state.get("block_message") or "I can only help with Dubai real-estate analysis."
        final = {
            "answer": message,
            "citations": {"row_count": 0, "tables": [], "sql": "", "filters": "", "date_range": None},
            "verification": {"verified": False, "confidence": "low", "numbers_checked": 0,
                             "verified_count": 0, "unverified_claims": [], "known_value_count": 0,
                             "reason": f"Request blocked by input guardrail ({state.get('block_category')})."},
            "confidence": "low", "low_confidence": True, "route": "blocked",
            "sql": "", "facts": [], "trend": None, "ranking": None,
            "notes": [], "retries": 0, "language": state.get("language", "en"),
            "blocked": True,
        }
        snap = telemetry.snapshot()
        final["request_id"] = snap.get("request_id", "")
        final["telemetry"] = snap
        await emit_event("orchestrator", "complete", "Request refused by guardrail.",
                         type="final", **final)
        return {"final": final}

    def _guard_selector(self, state: OrchestratorState) -> str:
        return "blocked" if state.get("blocked") else "ok"

    async def _query_node(self, state: OrchestratorState) -> dict:
        query_out = await self.query_agent.run(state["question"], state.get("history"))
        return {"query_out": query_out}

    async def _route_node(self, state: OrchestratorState) -> dict:
        route = self._decide_route(state["question"], state.get("query_out", {}))
        detail = (
            "Analytical question → Query · Analysis · Narrative · Verify"
            if route == "analytical"
            else "Simple lookup → Query · Narrative · Verify (analysis skipped)"
        )
        await emit_event("orchestrator", "complete", detail, route=route)
        return {"route": route}

    async def _analysis_node(self, state: OrchestratorState) -> dict:
        analysis = await self.analysis_agent.run(state["question"], state["query_out"]["result"])
        return {"analysis": analysis}

    async def _narrative_node(self, state: OrchestratorState) -> dict:
        question = state["question"]
        feedback = state.get("verifier_feedback")
        if feedback:
            question = (
                f"{question}\n\n[Reviewer correction: your previous answer contained figures that "
                f"could NOT be verified against the data: {feedback}. Re-write using ONLY the FACTS "
                f"and DATA provided; drop or qualify any figure not present there.]"
            )
        analysis = state.get("analysis", {"facts": [], "notes": []})
        out = await self.narrative_agent.run(
            question, state["query_out"], analysis,
            language=state.get("language", "en"), history=state.get("history"),
        )
        return {"narrative": out["narrative"], "citations": out["citations"]}

    async def _verify_node(self, state: OrchestratorState) -> dict:
        verification = await self.verifier.run(
            state["narrative"], state["query_out"], state.get("analysis", {})
        )
        retries = state.get("retries", 0)
        # Recompute the retry decision fresh every pass so stale state can't loop.
        should_retry = (
            not verification["verified"]
            and verification["confidence"] == "low"
            and retries < MAX_RETRIES
        )
        out: dict[str, Any] = {"verification": verification, "should_retry": should_retry}
        if should_retry:
            unmatched = ", ".join(str(c["value"]) for c in verification["unverified_claims"][:5])
            out["retries"] = retries + 1
            out["verifier_feedback"] = unmatched or "unspecified figures"
            await emit_event(
                "orchestrator", "running",
                f"Verifier flagged low confidence — regenerating answer (attempt {retries + 2})…",
            )
        return out

    async def _finalize_node(self, state: OrchestratorState) -> dict:
        verification = state.get("verification", {})
        analysis = state.get("analysis", {})
        final = {
            "answer": state.get("narrative", ""),
            "citations": state.get("citations", {}),
            "verification": verification,
            "confidence": verification.get("confidence", "low"),
            "low_confidence": not verification.get("verified", False),
            "route": state.get("route", "simple"),
            "sql": state.get("query_out", {}).get("result", {}).get("sql", ""),
            "facts": analysis.get("facts", []),
            "trend": analysis.get("trend"),
            "ranking": analysis.get("ranking"),
            "notes": analysis.get("notes", []),
            "retries": state.get("retries", 0),
            "language": state.get("language", "en"),
        }
        snap = telemetry.snapshot()
        final["request_id"] = snap.get("request_id", "")
        final["telemetry"] = snap
        await emit_event(
            "orchestrator", "complete", "Answer finalised.",
            type="final", **final,
        )
        return {"final": final}

    # --------------------------- selectors ---------------------------- #
    def _route_selector(self, state: OrchestratorState) -> str:
        return "analysis" if state.get("route") == "analytical" else "narrative"

    def _verify_selector(self, state: OrchestratorState) -> str:
        # Read only the freshly-computed signal from the verify node.
        return "retry" if state.get("should_retry") else "finalize"

    @staticmethod
    def _decide_route(question: str, query_out: dict) -> str:
        q = question.lower()
        if any(trig in q for trig in _ANALYTICAL_TRIGGERS):
            return "analytical"
        # Result-shape heuristic: a time series or a multi-row breakdown is analytical.
        result = query_out.get("result", {})
        rows, cols = result.get("rows", []), result.get("columns", [])
        time_like = any(c in cols for c in ("year_month", "month_date", "quarter", "year"))
        if time_like and len(rows) >= 3:
            return "analytical"
        if len(rows) >= 3 and len(cols) >= 2:
            return "analytical"
        return "simple"

    # ------------------------------ run ------------------------------- #
    @staticmethod
    def _resolve_language(question: str, language: str) -> str:
        if language in ("en", "ar"):
            return language
        # auto: detect Arabic script in the question
        if any("؀" <= ch <= "ۿ" for ch in question):
            return "ar"
        return "en"

    async def run(self, question: str, stream: AgentEventStream | None = None,
                  history: list | None = None, language: str = "auto") -> dict:
        """Run the full graph. If a stream is given, agent events are emitted to it."""
        resolved_language = self._resolve_language(question, language)

        async def _invoke() -> dict:
            telemetry.start_request(question)
            await emit_event("orchestrator", "running", "Received question — planning the investigation…")
            state: OrchestratorState = {
                "question": question, "retries": 0,
                "history": history or [], "language": resolved_language,
            }
            # recursion_limit is a defensive backstop; the retry path is already
            # bounded by MAX_RETRIES via the should_retry signal.
            final_state = await self.graph.ainvoke(state, config={"recursion_limit": 12})
            final = final_state.get("final", {})
            telemetry.finish_request(final)
            return final

        if stream is not None:
            with use_emitter(stream):
                return await _invoke()
        return await _invoke()
