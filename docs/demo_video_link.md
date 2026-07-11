# Demo Walkthrough

> Placeholder for the recorded product walkthrough. Add the link after recording.

**Video:** _<add YouTube / Loom link here>_

## Suggested 3–4 minute script

1. **The problem (20s).** Generic "chatbot over a CSV" projects answer questions but can't
   be trusted — they hallucinate numbers and hide their reasoning. DubaiPulse is built to be
   *trustworthy*: it investigates, cites, and verifies.
2. **Ask an analytical question (60s).** e.g. *"Which zones saw the biggest price increase in 2024?"*
   Point at the **live Reasoning Trace** — Query Agent writing SQL, Analysis Agent flagging
   trends/anomalies, Narrative Agent writing, Verifier confirming figures.
3. **Show the guardrail (45s).** Expand the SQL behind the answer and the **verification badge**
   (e.g. "Verified 4/4 · high confidence"). Explain the Verifier checks every number against the
   queried data, not by asking the LLM to re-check itself.
4. **Show a caveat (30s).** Ask a yield question and show the honest *"gross yield — excludes
   service charges"* note. Honesty is a credibility signal.
5. **Dashboard + architecture (30s).** Pan the KPI dashboard, then the architecture diagram —
   orchestrator + specialist agents + verifier, streamed over SSE, React/FastAPI stack.

## Screenshots to capture for the README

- `docs/screenshot_trace.png` — the Reasoning Trace panel mid-stream.
- `docs/screenshot_answer.png` — a finished answer with the citation + confidence badge.
