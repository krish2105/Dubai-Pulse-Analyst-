// API client: base URL + API-key header, an insights fetch, and a POST-based
// SSE reader (EventSource can't POST, so we stream the fetch body ourselves).

import type { AgentEvent, Insights } from "./types";

const BASE_URL = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
const API_KEY = import.meta.env.VITE_API_KEY || "";

function headers(extra?: Record<string, string>): Record<string, string> {
  const h: Record<string, string> = { ...extra };
  if (API_KEY) h["X-API-Key"] = API_KEY;
  return h;
}

export async function fetchInsights(): Promise<Insights> {
  const res = await fetch(`${BASE_URL}/insights`, { headers: headers() });
  if (!res.ok) throw new Error(`Insights request failed: ${res.status}`);
  return res.json();
}

/**
 * POST a question to /chat and stream Server-Sent Events.
 * Calls `onEvent` for each parsed event. Returns when the stream ends.
 * Pass an AbortController signal to cancel.
 */
export async function streamChat(
  question: string,
  onEvent: (event: AgentEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${BASE_URL}/chat`, {
    method: "POST",
    headers: headers({ "Content-Type": "application/json", Accept: "text/event-stream" }),
    body: JSON.stringify({ question }),
    signal,
  });

  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const j = await res.json();
      detail = typeof j.detail === "string" ? j.detail : detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  if (!res.body) throw new Error("No response stream from server.");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  // Parse SSE frames separated by a blank line. Each frame has `event:` + `data:`.
  const flush = (frame: string) => {
    let eventType = "message";
    const dataLines: string[] = [];
    for (const line of frame.split("\n")) {
      if (line.startsWith("event:")) eventType = line.slice(6).trim();
      else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
    }
    if (!dataLines.length) return;
    const raw = dataLines.join("\n");
    if (raw === "{}") return; // 'done' marker
    try {
      const parsed = JSON.parse(raw);
      onEvent({ ...parsed, type: parsed.type || eventType } as AgentEvent);
    } catch {
      /* ignore malformed frame */
    }
  };

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      if (frame.trim()) flush(frame);
    }
  }
  if (buffer.trim()) flush(buffer);
}
