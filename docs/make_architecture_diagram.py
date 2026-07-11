"""Generate docs/architecture_diagram.png (the Section-5 flow). Run: python make_architecture_diagram.py"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

INK, INK2, GOLD, BRAND, CYAN, GREEN, PURPLE, TXT, MUT = (
    "#0f1524", "#161d30", "#e0a92e", "#2f7bff", "#22d3ee", "#34d399", "#a78bfa", "#e8edf7", "#94a3b8"
)

fig, ax = plt.subplots(figsize=(12, 8.6), dpi=150)
fig.patch.set_facecolor("#0a0e1a")
ax.set_facecolor("#0a0e1a")
ax.set_xlim(0, 12); ax.set_ylim(0, 8.6); ax.axis("off")


def box(x, y, w, h, title, sub="", fc=INK2, ec=BRAND, tc=TXT, bold=True, fs=11):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.04,rounding_size=0.12",
                                fc=fc, ec=ec, lw=1.8))
    ax.text(x + w / 2, y + h / 2 + (0.16 if sub else 0), title, ha="center", va="center",
            color=tc, fontsize=fs, fontweight="bold" if bold else "normal")
    if sub:
        ax.text(x + w / 2, y + h / 2 - 0.28, sub, ha="center", va="center", color=MUT, fontsize=8.5)


def arrow(x1, y1, x2, y2, color=GOLD, style="-|>", lw=2.0, ls="-"):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=16,
                                 color=color, lw=lw, linestyle=ls, shrinkA=2, shrinkB=2))


ax.text(6, 8.25, "DubaiPulse Analyst — System Architecture", ha="center",
        color=GOLD, fontsize=16, fontweight="bold")
ax.text(6, 7.9, "Multi-agent, grounded, verified market-intelligence copilot", ha="center",
        color=MUT, fontsize=10)

# Frontend
box(0.6, 6.5, 3.4, 1.0, "React + TypeScript (Vercel)",
    "Chat · live Reasoning Trace · Citations · KPI dashboard", ec=BRAND)
# Backend container
box(8.0, 6.5, 3.4, 1.0, "FastAPI (Docker · Railway/Render)",
    "SSE · API-key auth · rate limit · logging", ec=GREEN)

arrow(4.0, 7.15, 8.0, 7.15, color=BRAND); ax.text(6, 7.32, "POST /chat  {question}", ha="center", color=BRAND, fontsize=8.5)
arrow(8.0, 6.75, 4.0, 6.75, color=GOLD); ax.text(6, 6.55, "SSE  ← agent step events + final answer", ha="center", color=GOLD, fontsize=8.5)

# Orchestrator
box(3.5, 5.0, 5.0, 0.95, "LangGraph Orchestrator",
    "state machine · conditional routing · retry-on-low-confidence", ec=GOLD)
arrow(9.7, 6.5, 8.2, 5.95, color=GREEN)

# Agents row
box(0.4, 3.0, 2.5, 1.1, "Query Agent", "NL → DuckDB SQL\n(safe, read-only)", ec=GREEN, fs=10.5)
box(3.15, 3.0, 2.5, 1.1, "Analysis Agent", "trends · anomalies\n(z-score) · ranking", ec=GOLD, fs=10.5)
box(5.9, 3.0, 2.5, 1.1, "Narrative Agent", "executive answer\n(grounded prose)", ec=PURPLE, fs=10.5)
box(8.65, 3.0, 2.9, 1.1, "Verifier", "checks every number\nvs source data", ec=CYAN, fs=10.5)

# Orchestrator fans out to each agent (clean vertical connectors).
for cx in (1.65, 4.4, 7.15, 10.1):
    arrow(cx, 4.98, cx, 4.12, color=MUT, lw=1.3, ls=(0, (3, 3)))

# retry loop (verifier -> narrative)
arrow(9.8, 4.1, 7.15, 4.55, color="#f87171", lw=1.6, ls=(0, (2, 2)))
ax.text(8.5, 4.68, "retry if low confidence", ha="center", color="#f87171", fontsize=8)

# Data layer
box(0.4, 1.2, 5.2, 1.1, "DuckDB Query Engine",
    "transactions (87k) · area_monthly · metro_stations  (Parquet)", ec=GREEN)
box(6.1, 1.2, 5.45, 1.1, "Claude API (Sonnet) — Anthropic SDK",
    "NL→SQL  ·  narrative generation", ec=PURPLE)

arrow(1.65, 3.0, 2.6, 2.3, color=GREEN, lw=1.6)          # query agent -> duckdb
arrow(10.1, 3.0, 9.3, 2.3, color=CYAN, lw=1.6)           # verifier -> duckdb? -> checks data
arrow(9.6, 3.05, 8.8, 2.3, color=PURPLE, lw=1.4)         # narrative -> claude
arrow(1.9, 3.0, 6.4, 2.3, color=GREEN, lw=1.0, ls=(0, (2, 3)))

ax.text(3.0, 0.72, "Real Kaggle dataset (CC0) · Dubai secondary/off-plan/rentals · Jan 2020–Apr 2026",
        ha="center", color=MUT, fontsize=8.5)

out = Path(__file__).parent / "architecture_diagram.png"
plt.savefig(out, bbox_inches="tight", facecolor=fig.get_facecolor(), pad_inches=0.25)
print("wrote", out)
