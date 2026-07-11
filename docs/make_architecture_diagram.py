"""Generate docs/architecture_diagram.png. Run: python make_architecture_diagram.py"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

INK2, GOLD, BRAND, CYAN, GREEN, PURPLE, ROSE, INDIGO, TXT, MUT = (
    "#161d30", "#e0a92e", "#2f7bff", "#22d3ee", "#34d399", "#a78bfa",
    "#f87171", "#818cf8", "#e8edf7", "#94a3b8",
)

fig, ax = plt.subplots(figsize=(13, 9), dpi=150)
fig.patch.set_facecolor("#0a0e1a")
ax.set_facecolor("#0a0e1a")
ax.set_xlim(0, 13); ax.set_ylim(0, 9); ax.axis("off")


def box(x, y, w, h, title, sub="", ec=BRAND, fs=10.5, tc=TXT):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.03,rounding_size=0.1",
                                fc=INK2, ec=ec, lw=1.6))
    ax.text(x + w / 2, y + h / 2 + (0.13 if sub else 0), title, ha="center", va="center",
            color=tc, fontsize=fs, fontweight="bold")
    if sub:
        ax.text(x + w / 2, y + h / 2 - 0.22, sub, ha="center", va="center", color=MUT, fontsize=7.5)


def arrow(x1, y1, x2, y2, color=GOLD, lw=1.9, ls="-", style="-|>"):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=14,
                                 color=color, lw=lw, linestyle=ls, shrinkA=2, shrinkB=2))


ax.text(6.5, 8.6, "DubaiPulse Analyst — System Architecture", ha="center",
        color=GOLD, fontsize=16, fontweight="bold")
ax.text(6.5, 8.25, "Multi-agent · grounded · verified · observable · hardened", ha="center",
        color=MUT, fontsize=10)

# Frontend / Backend
box(0.5, 6.9, 3.7, 1.0, "React + TypeScript (Vercel)",
    "chat · live trace · charts · map · light/dark · EN/عربي", ec=BRAND)
box(8.8, 6.9, 3.7, 1.0, "FastAPI (Docker · Railway/Render)",
    "SSE · API-key · security headers · rate limit · concurrency", ec=GREEN)
arrow(4.2, 7.55, 8.8, 7.55, color=BRAND); ax.text(6.5, 7.72, "POST /chat", ha="center", color=BRAND, fontsize=8)
arrow(8.8, 7.15, 4.2, 7.15, color=GOLD); ax.text(6.5, 6.98, "SSE ← steps · tokens · answer", ha="center", color=GOLD, fontsize=8)

# Orchestrator
box(4.3, 5.55, 4.4, 0.85, "LangGraph Orchestrator",
    "state machine · routing · retry-on-low-confidence", ec=GOLD)
arrow(10.6, 6.9, 8.7, 6.4, color=GREEN)

# Agent pipeline (horizontal)
pipe = [
    ("Guardrail", "injection /\nSQL-write block", ROSE),
    ("Query", "NL → SQL\n(read-only)", GREEN),
    ("Analysis", "trends /\nanomalies", GOLD),
    ("Context", "RAG: market\nevents (BM25)", INDIGO),
    ("Narrative", "grounded\nanswer", PURPLE),
    ("Verifier", "checks every\nnumber", CYAN),
]
w = 1.95; gap = 0.13; x0 = 0.35
y = 3.7
for i, (t, s, ec) in enumerate(pipe):
    x = x0 + i * (w + gap)
    box(x, y, w, 1.05, t, s, ec=ec, fs=10)
    if i > 0:
        arrow(x - gap - 0.02, y + 0.52, x + 0.02, y + 0.52, color=MUT, lw=1.3)
# orchestrator down into pipeline
arrow(6.5, 5.55, 6.5, 4.78, color=MUT, lw=1.3, ls=(0, (3, 3)))
# retry loop verifier -> narrative
arrow(pipe_x := x0 + 5 * (w + gap) + w / 2, y, x0 + 4 * (w + gap) + w / 2, y - 0.02, color=ROSE, lw=0, ls="-")
ax.text(6.5, 3.5, "↺ low confidence → regenerate once", ha="center", color=ROSE, fontsize=7.5)

# Data / knowledge / LLM / observability
box(0.35, 1.7, 3.0, 1.0, "DuckDB + Parquet",
    "transactions 87k · area_monthly · metro", ec=GREEN)
box(3.6, 1.7, 2.9, 1.0, "Knowledge base",
    "dated market events (RAG)", ec=INDIGO)
box(6.75, 1.7, 2.7, 1.0, "LLM provider",
    "Ollama/Groq/Gemini/…", ec=PURPLE)
box(9.7, 1.7, 2.95, 1.0, "Observability",
    "/metrics · tokens · latency · feedback · audit log", ec=CYAN)

arrow(1.3, 3.7, 1.5, 2.7, color=GREEN, lw=1.3)          # query -> duckdb
arrow(6.4, 3.7, 5.2, 2.7, color=INDIGO, lw=1.3)         # context -> KB
arrow(8.4, 3.7, 8.0, 2.7, color=PURPLE, lw=1.3)         # narrative -> LLM
arrow(9.5, 5.55, 11.1, 2.72, color=CYAN, lw=1.0, ls=(0, (2, 3)))  # telemetry

ax.text(6.5, 0.95, "Real Kaggle dataset (CC0) · Dubai secondary/off-plan/rentals · Jan 2020 – Apr 2026",
        ha="center", color=MUT, fontsize=8.5)

out = Path(__file__).parent / "architecture_diagram.png"
plt.savefig(out, bbox_inches="tight", facecolor=fig.get_facecolor(), pad_inches=0.25)
print("wrote", out)
