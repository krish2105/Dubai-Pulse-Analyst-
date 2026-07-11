// ReasoningTracePanel — the standout feature. Renders each agent's step live as
// it streams in, with per-agent status, timing and expandable detail (SQL,
// row counts, facts, verification). Collapsible.

import { useState } from "react";
import {
  ChevronDown, ChevronRight, Database, LineChart, PenLine, ShieldCheck, ShieldAlert,
  Workflow, CheckCircle2, Loader2, XCircle, MinusCircle, BookOpen,
} from "lucide-react";
import type { AgentEvent } from "../lib/types";

const AGENT_META: Record<string, { label: string; icon: any; color: string }> = {
  guardrail: { label: "Guardrail", icon: ShieldAlert, color: "text-rose-400" },
  orchestrator: { label: "Orchestrator", icon: Workflow, color: "text-accent-blue" },
  query_agent: { label: "Query Agent", icon: Database, color: "text-emerald-400" },
  analysis_agent: { label: "Analysis Agent", icon: LineChart, color: "text-accent-gold" },
  context_agent: { label: "Context (RAG)", icon: BookOpen, color: "text-indigo-400" },
  narrative_agent: { label: "Narrative Agent", icon: PenLine, color: "text-purple-400" },
  verifier: { label: "Verifier", icon: ShieldCheck, color: "text-cyan-400" },
};

function StatusIcon({ status }: { status: string }) {
  if (status === "running") return <Loader2 className="h-3.5 w-3.5 animate-spin text-muted" />;
  if (status === "complete") return <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />;
  if (status === "error") return <XCircle className="h-3.5 w-3.5 text-rose-400" />;
  return <MinusCircle className="h-3.5 w-3.5 text-faint" />;
}

function StepDetail({ event }: { event: AgentEvent }) {
  const d = event.data || {};
  return (
    <div className="mt-1.5 ml-6 space-y-1.5 text-xs text-muted">
      {d.sql && (
        <pre className="overflow-x-auto rounded-md bg-page border border-line p-2 font-mono text-[11px] text-emerald-300">
          {d.sql}
        </pre>
      )}
      {typeof d.row_count === "number" && (
        <div>
          Rows returned: <span className="text-content">{d.row_count}</span>
          {d.filters_summary ? <> · Filters: <span className="text-content">{d.filters_summary}</span></> : null}
        </div>
      )}
      {Array.isArray(d.facts) && d.facts.length > 0 && (
        <ul className="list-disc pl-4 space-y-0.5">
          {d.facts.slice(0, 5).map((f: string, i: number) => <li key={i}>{f}</li>)}
        </ul>
      )}
      {Array.isArray(d.events) && d.events.length > 0 && (
        <ul className="space-y-0.5">
          {d.events.map((e: any, i: number) => (
            <li key={i}>
              📎 <span className="text-content">{e.date} · {e.title}</span>
              <span className="opacity-70"> — {e.source}</span>
            </li>
          ))}
        </ul>
      )}
      {typeof d.numbers_checked === "number" && (
        <div>
          Figures verified: <span className="text-content">{d.verified_count}/{d.numbers_checked}</span>
          {" · "}confidence:{" "}
          <span className={
            d.confidence === "high" ? "text-emerald-400"
              : d.confidence === "medium" ? "text-accent-gold" : "text-rose-400"
          }>{d.confidence}</span>
          {Array.isArray(d.unverified_claims) && d.unverified_claims.length > 0 && (
            <div className="mt-1 text-rose-300">
              Unverified: {d.unverified_claims.map((c: any) => c.value).join(", ")}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function ReasoningTracePanel({
  steps, streaming,
}: {
  steps: AgentEvent[];
  streaming: boolean;
}) {
  const [open, setOpen] = useState(true);
  const visible = steps.filter((s) => s.type === "agent_step");
  if (visible.length === 0 && !streaming) return null;

  return (
    <div className="mt-3 rounded-lg border border-line bg-surface/60">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs font-medium text-content hover:text-bright"
      >
        {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        <Workflow className="h-4 w-4 text-accent-blue" />
        Reasoning trace
        <span className="ml-1 rounded-full bg-elevated px-2 py-0.5 text-[10px] text-muted">
          {visible.length} step{visible.length === 1 ? "" : "s"}
        </span>
        {streaming && (
          <span className="ml-auto flex items-center gap-1 text-[10px] text-accent-blue">
            <span className="h-1.5 w-1.5 rounded-full bg-brand-400 animate-pulse-dot" /> live
          </span>
        )}
      </button>

      {open && (
        <div className="space-y-2 px-3 pb-3">
          {visible.map((event, i) => {
            const meta = AGENT_META[event.agent] || {
              label: event.agent, icon: Workflow, color: "text-muted",
            };
            const Icon = meta.icon;
            const hasDetail =
              event.data &&
              (event.data.sql || event.data.row_count !== undefined ||
                (event.data.facts && event.data.facts.length) ||
                (event.data.events && event.data.events.length) ||
                event.data.numbers_checked !== undefined);
            return (
              <div key={i} className="animate-fade-in">
                <div className="flex items-center gap-2 text-xs">
                  <Icon className={`h-4 w-4 shrink-0 ${meta.color}`} />
                  <span className="font-medium text-content">{meta.label}</span>
                  <StatusIcon status={event.status} />
                  <span className="truncate text-muted">{event.detail}</span>
                </div>
                {hasDetail && <StepDetail event={event} />}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
