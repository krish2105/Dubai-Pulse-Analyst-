"""
Input Guardrail — the first line of defence (OWASP LLM01: Prompt Injection).

A deterministic firewall that inspects the user's question BEFORE it reaches the
NL→SQL step. It blocks:
  * prompt-injection / jailbreak attempts ("ignore previous instructions", …),
  * attempts to exfiltrate the system prompt / config (LLM07),
  * SQL-write / destructive intent (defence-in-depth on top of the read-only
    DuckDB engine),
  * excessively long inputs (LLM10: unbounded consumption).

It is deterministic (regex/heuristics) — no LLM call, no latency, no cost — which
is exactly the "prepared-statement" style guardrail recommended for text-to-SQL
agents. Blocked requests get a clear, safe refusal instead of running the pipeline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.agents.events import emit_event

# --- Prompt injection / jailbreak phrases ------------------------------------ #
_INJECTION = re.compile(
    r"\b(ignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions|prompts?|rules)"
    r"|disregard\s+(the\s+)?(instructions|rules|system)"
    r"|forget\s+(everything|all|your\s+instructions)"
    r"|you\s+are\s+now\b|act\s+as\s+(a\s+)?(dan|jailbreak)"
    r"|developer\s+mode|jailbreak"
    r"|reveal\s+(your|the)\s+(system\s+)?(prompt|instructions|rules)"
    r"|(print|show|repeat|output)\s+(your|the)\s+(system\s+)?(prompt|instructions)"
    r"|what\s+(is|are)\s+your\s+(system\s+)?(prompt|instructions|rules))\b",
    re.IGNORECASE,
)

# --- Destructive / write SQL intent (defence in depth) ----------------------- #
_SQL_WRITE = re.compile(
    r"\b(drop\s+table|delete\s+from|insert\s+into|update\s+\w+\s+set|truncate\s+table"
    r"|alter\s+table|create\s+table|;\s*drop|--\s|/\*|xp_cmdshell|union\s+select)\b",
    re.IGNORECASE,
)

# --- Obvious abuse / unsafe content ------------------------------------------ #
_UNSAFE = re.compile(
    r"\b(hack|malware|ransomware|exploit\s+the|bomb|weapon)\b", re.IGNORECASE
)

MAX_QUESTION_CHARS = 500


@dataclass
class GuardVerdict:
    allowed: bool
    category: str  # 'ok' | 'injection' | 'sql_write' | 'unsafe' | 'too_long'
    message: str


_REFUSALS = {
    "injection": "I can only answer questions about the Dubai real-estate dataset. "
                 "I can't change my instructions or reveal system configuration.",
    "sql_write": "This assistant is strictly read-only — it can't modify or delete data. "
                 "Ask me to analyse or compare figures instead.",
    "unsafe": "I can only help with Dubai real-estate market analysis.",
    "too_long": "That question is too long — please keep it under 500 characters.",
}


class InputGuardrail:
    def classify(self, question: str) -> GuardVerdict:
        q = (question or "").strip()
        if len(q) > MAX_QUESTION_CHARS:
            return GuardVerdict(False, "too_long", _REFUSALS["too_long"])
        if _INJECTION.search(q):
            return GuardVerdict(False, "injection", _REFUSALS["injection"])
        if _SQL_WRITE.search(q):
            return GuardVerdict(False, "sql_write", _REFUSALS["sql_write"])
        if _UNSAFE.search(q):
            return GuardVerdict(False, "unsafe", _REFUSALS["unsafe"])
        return GuardVerdict(True, "ok", "")

    async def run(self, question: str) -> GuardVerdict:
        await emit_event("guardrail", "running", "Screening the request…")
        verdict = self.classify(question)
        if verdict.allowed:
            await emit_event("guardrail", "complete", "Request passed safety checks.")
        else:
            await emit_event(
                "guardrail", "error", f"Blocked ({verdict.category}).",
                category=verdict.category,
            )
        return verdict
