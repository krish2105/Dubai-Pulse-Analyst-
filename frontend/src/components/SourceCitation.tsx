// SourceCitation — provenance behind an answer (row count, date range, filters,
// SQL), the verifier confidence badge, an observability line (latency / tokens /
// cost / model), and 👍/👎 feedback.

import { useState } from "react";
import {
  AlertTriangle, ShieldCheck, Code2, ChevronDown, ChevronRight, Database,
  Zap, ThumbsUp, ThumbsDown, BookOpen,
} from "lucide-react";
import type { FinalAnswer } from "../lib/types";
import { sendFeedback } from "../lib/api";

function ConfidenceBadge({ final }: { final: FinalAnswer }) {
  const c = final.confidence;
  const map = {
    high: { cls: "bg-emerald-500/15 text-emerald-500 border-emerald-500/30", label: "Verified · high confidence", icon: ShieldCheck },
    medium: { cls: "bg-gold-500/15 text-accent-gold border-gold-500/30", label: "Partially verified · medium confidence", icon: ShieldCheck },
    low: { cls: "bg-rose-500/15 text-rose-500 border-rose-500/30", label: "Low confidence — figures not fully verified", icon: AlertTriangle },
  } as const;
  const m = map[c] || map.low;
  const Icon = m.icon;
  return (
    <div className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${m.cls}`}>
      <Icon className="h-3.5 w-3.5" />
      {m.label}
      {final.verification?.numbers_checked > 0 && (
        <span className="opacity-70">
          ({final.verification.verified_count}/{final.verification.numbers_checked})
        </span>
      )}
    </div>
  );
}

function Feedback({ requestId }: { requestId?: string }) {
  const [sent, setSent] = useState<"up" | "down" | null>(null);
  if (!requestId) return null;
  const click = (r: "up" | "down") => {
    if (sent) return;
    setSent(r);
    sendFeedback(requestId, r);
  };
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-[11px] text-faint">{sent ? "Thanks!" : "Helpful?"}</span>
      <button
        onClick={() => click("up")}
        disabled={!!sent}
        className={`rounded p-1 transition ${sent === "up" ? "text-emerald-500" : "text-faint hover:text-emerald-500"}`}
        title="Helpful"
      >
        <ThumbsUp className="h-3.5 w-3.5" />
      </button>
      <button
        onClick={() => click("down")}
        disabled={!!sent}
        className={`rounded p-1 transition ${sent === "down" ? "text-rose-500" : "text-faint hover:text-rose-500"}`}
        title="Not helpful"
      >
        <ThumbsDown className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

export default function SourceCitation({ final }: { final: FinalAnswer }) {
  const [showSql, setShowSql] = useState(false);
  const cit = final.citations;
  const tel = final.telemetry;
  if (!cit) return null;

  return (
    <div className="mt-3 space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <ConfidenceBadge final={final} />
        {final.low_confidence && !final.blocked && (
          <span className="text-[11px] text-rose-500/80">{final.verification?.reason}</span>
        )}
        <div className="ml-auto"><Feedback requestId={final.request_id} /></div>
      </div>

      {cit.row_count > 0 && (
        <div className="rounded-lg border border-line bg-surface/40 p-3 text-xs text-muted">
          <div className="mb-1.5 flex items-center gap-1.5 font-medium text-content">
            <Database className="h-3.5 w-3.5 text-accent-blue" /> Source
          </div>
          <div className="grid grid-cols-1 gap-1 sm:grid-cols-2">
            <div>Rows analysed: <span className="text-content">{cit.row_count}{cit.truncated ? "+ (capped)" : ""}</span></div>
            {cit.date_range && (
              <div>Date range: <span className="text-content">{cit.date_range.min} → {cit.date_range.max}</span></div>
            )}
            {cit.filters && <div className="sm:col-span-2">Filters: <span className="text-content">{cit.filters}</span></div>}
            {cit.tables?.length > 0 && <div>Tables: <span className="text-content">{cit.tables.join(", ")}</span></div>}
            <div>Route: <span className="text-content">{final.route}</span>{final.retries > 0 ? ` · ${final.retries} retry` : ""}</div>
          </div>

          {cit.sql && (
            <div className="mt-2">
              <button
                onClick={() => setShowSql((s) => !s)}
                className="flex items-center gap-1 text-[11px] text-muted hover:text-bright"
              >
                {showSql ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                <Code2 className="h-3.5 w-3.5" /> View the SQL that produced this answer
              </button>
              {showSql && (
                <pre className="mt-1.5 overflow-x-auto rounded-md border border-line bg-page p-2 font-mono text-[11px] text-emerald-500">
                  {cit.sql}
                </pre>
              )}
            </div>
          )}

          {tel && (
            <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-line pt-2 text-[11px] text-faint">
              <span className="flex items-center gap-1"><Zap className="h-3 w-3 text-accent-gold" /> {tel.latency_ms} ms</span>
              <span>{tel.llm_calls} LLM call{tel.llm_calls === 1 ? "" : "s"}</span>
              <span>~{tel.est_total_tokens.toLocaleString()} tokens</span>
              {tel.est_cost_usd > 0 && <span>${tel.est_cost_usd.toFixed(4)}</span>}
              <span className="ml-auto opacity-80">{tel.provider} · {tel.model}</span>
            </div>
          )}
        </div>
      )}

      {final.context_sources && final.context_sources.length > 0 && (
        <div className="rounded-lg border border-line bg-surface/40 p-3 text-xs text-muted">
          <div className="mb-1.5 flex items-center gap-1.5 font-medium text-content">
            <BookOpen className="h-3.5 w-3.5 text-indigo-400" /> Market context (RAG)
          </div>
          {final.context_sources.map((e) => (
            <div key={e.id}>
              • <span className="text-content">{e.date} · {e.title}</span>
              <span className="opacity-70"> — {e.source}</span>
            </div>
          ))}
        </div>
      )}

      {final.notes?.length > 0 && (
        <div className="rounded-lg border border-gold-500/20 bg-gold-500/5 p-2.5 text-[11px] text-accent-gold/90">
          {final.notes.map((n, i) => <div key={i}>⚠ {n}</div>)}
        </div>
      )}
    </div>
  );
}
