# DubaiPulse Analyst — Evaluation Benchmark

A fixed set of natural-language questions the system must answer well, plus the KPIs the
Analysis Agent must be able to compute. These drive `backend/tests/test_agents.py` and the
manual demo script. We evaluate **behaviour and grounding** (correct routing, non-empty
citations, verifier confirmation, numbers traceable to data) rather than exact wording,
because LLM phrasing varies.

---

## Benchmark questions

| # | Question | Type | Expected routing | What a good answer contains |
|---|----------|------|------------------|-----------------------------|
| Q1 | *Which zones saw the biggest price increase in 2024?* | trend / ranking | Query → Analysis → Narrative → Verifier | A ranked list of zones with YoY/annual % change, grounded in `area_monthly`; top movers named with numbers. |
| Q2 | *Why did off-plan transaction volume change in early 2022?* | causal / trend | Query → Analysis → Narrative → Verifier | Monthly off-plan volume series around early 2022, macro context (base rate, Golden Visa timing), honest "correlation not causation" caveat. |
| Q3 | *Compare rental yields across Downtown Dubai and Dubai Marina in 2025.* | comparison | Query → Analysis → Narrative → Verifier | Gross yield % for both communities, difference stated, gross-yield caveat (no service charges). |
| Q4 | *What is the average price per sqft in Palm Jumeirah for secondary sales in 2025?* | simple lookup | Query → Narrative → Verifier (Analysis skipped) | A single grounded number with row count + filters. |
| Q5 | *How did the CBUAE base rate relate to secondary price growth from 2022 to 2024?* | causal / correlation | Query → Analysis → Narrative → Verifier | Rate path vs price/sqft path, direction of relationship, causation caveat. |
| Q6 | *Which communities offer the highest rental yield in 2025, and what's the trade-off?* | ranking + reasoning | Query → Analysis → Narrative → Verifier | Top-yield communities with % , note that high gross yield often = lower-price / higher-risk areas. |
| Q7 | *Compare off-plan vs secondary price per sqft in Business Bay over 2023–2025.* | comparison / trend | Query → Analysis → Narrative → Verifier | Both series, premium/discount of off-plan, trend direction. |
| Q8 | *What was the cheapest apartment community by price per sqft in 2025?* (ambiguity/robustness probe) | simple lookup / edge | Query → Narrative → Verifier | A grounded answer; if the question is under-specified the system asks a clarifying note rather than hallucinating. |

---

## KPIs the Analysis Agent must compute

1. **Average price per sqft by zone / community** — level and ranking.
2. **Transaction volume** — monthly listing counts, and change over a period.
3. **Rental yield (gross), %** — `rent/sqft ÷ price/sqft × 100`, by community.
4. **Month-over-month & year-over-year price change, %** — for the secondary price/sqft series.
5. **Anomaly flags** — rolling z-score (> 2σ from trailing mean) marking unusual months.

---

## Scoring rubric (per question)

Each answer is scored on five binary criteria (used in tests + manual review):

- **Grounded** — every number appears in the queried result set (Verifier confirms).
- **Routed correctly** — Analysis Agent invoked for trend/comparison; skipped for simple lookup.
- **Cited** — the answer carries row count, date range, and filters applied.
- **Honest** — limitations/caveats surfaced where relevant (gross yield, correlation ≠ causation, jittered coords).
- **Confidence-flagged** — if the Verifier cannot confirm a number, the answer is marked low-confidence, not presented as fact.

A question "passes" when it scores ≥ 4/5, with **Grounded** mandatory.
