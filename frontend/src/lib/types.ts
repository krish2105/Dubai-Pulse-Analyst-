// Shared types mirroring the backend SSE + REST contracts.

export type AgentName =
  | "orchestrator"
  | "query_agent"
  | "analysis_agent"
  | "narrative_agent"
  | "verifier";

export type StepStatus = "running" | "complete" | "skipped" | "error";

export interface AgentEvent {
  type: "agent_step" | "final" | "error" | "done" | "token";
  agent: AgentName | string;
  status: StepStatus;
  detail: string;
  data: Record<string, any>;
  ts: number;
}

export interface Citations {
  row_count: number;
  truncated: boolean;
  date_range: { column: string; min: string; max: string } | null;
  filters: string;
  tables: string[];
  sql: string;
}

export interface Verification {
  verified: boolean;
  confidence: "high" | "medium" | "low";
  numbers_checked: number;
  verified_count: number;
  unverified_claims: { value: number; is_percent?: boolean; context: string }[];
  known_value_count: number;
  reason: string;
}

export interface FinalAnswer {
  answer: string;
  citations: Citations;
  verification: Verification;
  confidence: "high" | "medium" | "low";
  low_confidence: boolean;
  route: "simple" | "analytical";
  sql: string;
  facts: string[];
  trend: any | null;
  ranking: any | null;
  notes: string[];
  retries: number;
  language?: string;
  blocked?: boolean;
  request_id?: string;
  telemetry?: {
    latency_ms: number;
    llm_calls: number;
    est_total_tokens: number;
    est_cost_usd: number;
    provider: string;
    model: string;
  };
}

// A chat message in the UI.
export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  steps: AgentEvent[];
  final?: FinalAnswer;
  error?: string;
  streaming: boolean;
  language?: string;
}

// /insights payload
export interface Insights {
  headline: {
    total_listings: number;
    secondary: number;
    offplan: number;
    rental: number;
    communities: number;
    zones: number;
    start_date: string;
    end_date: string;
  };
  price_trend: { year_month: string; price_per_sqft: number; base_rate: number }[];
  volume_by_year: { year: number; secondary: number; offplan: number; rental: number }[];
  top_zones: { zone: string; price_per_sqft: number }[];
  top_yield: { community: string; yield_pct: number }[];
}

export interface GeoPoint {
  community: string;
  zone: string;
  lat: number;
  lon: number;
  price_per_sqft: number | null;
  n_secondary: number;
  yield_pct: number | null;
  dist_km: number | null;
}

export interface Analytics {
  price_distribution: { bin: number; n: number }[];
  rate_vs_price: { year_month: string; base_rate: number; price_per_sqft: number }[];
  yield_vs_price: { community: string; price_per_sqft: number; yield_pct: number }[];
  seasonality: { month: number; avg_mom_pct: number }[];
  price_by_type: { property_type: string; price_per_sqft: number; n: number }[];
}
