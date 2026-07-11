"""
Market-events knowledge base + BM25 retrieval (the RAG layer).

Grounds "why" / causal answers in real, dated, sourced Dubai market events
(Golden Visa, CBUAE rate moves, Expo 2020, COVID, capital inflows, …) so the
Narrative Agent can explain *why* a trend happened and cite where it comes from
— instead of speculating. Retrieval is lexical BM25 (deterministic, no
embeddings/infra), which is plenty for a small curated corpus.
"""

from __future__ import annotations

import json
import re
import threading
from typing import Any

from rank_bm25 import BM25Okapi

from app.config import BACKEND_DIR

_EVENTS_PATH = BACKEND_DIR / "data" / "market_events.json"
_token_re = re.compile(r"[a-z0-9]+")


def _tok(text: str) -> list[str]:
    return _token_re.findall(text.lower())


class KnowledgeBase:
    _instance: KnowledgeBase | None = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = json.loads(_EVENTS_PATH.read_text())
        corpus = [
            _tok(f"{e['title']} {e['description']} {' '.join(e.get('tags', []))} {e.get('date','')}")
            for e in self.events
        ]
        self._bm25 = BM25Okapi(corpus)

    @classmethod
    def instance(cls) -> KnowledgeBase:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def retrieve(self, query: str, k: int = 3, min_score: float = 0.5) -> list[dict[str, Any]]:
        """Return the top-k relevant events (above a small score floor)."""
        if not query.strip():
            return []
        scores = self._bm25.get_scores(_tok(query))
        ranked = sorted(zip(scores, self.events, strict=False), key=lambda x: x[0], reverse=True)
        out = []
        for score, event in ranked[:k]:
            if score <= min_score:
                continue
            out.append({**event, "score": round(float(score), 3)})
        return out


def get_kb() -> KnowledgeBase:
    return KnowledgeBase.instance()
