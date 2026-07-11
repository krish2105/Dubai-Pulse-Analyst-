// useAgentStream — drives a POST /chat SSE conversation and exposes the live
// reasoning trace + final answer as React state. This is the glue behind the
// standout live-reasoning UI.

import { useCallback, useRef, useState } from "react";
import { streamChat } from "../lib/api";
import type { AgentEvent, ChatMessage, FinalAnswer } from "../lib/types";

let idSeq = 0;
const nextId = () => `m${Date.now()}_${idSeq++}`;

export function useAgentStream() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const patch = useCallback((id: string, update: (m: ChatMessage) => ChatMessage) => {
    setMessages((prev) => prev.map((m) => (m.id === id ? update(m) : m)));
  }, []);

  const ask = useCallback(
    async (question: string) => {
      if (isStreaming) return;
      const userMsg: ChatMessage = {
        id: nextId(), role: "user", content: question, steps: [], streaming: false,
      };
      const assistantId = nextId();
      const assistantMsg: ChatMessage = {
        id: assistantId, role: "assistant", content: "", steps: [], streaming: true,
      };
      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setIsStreaming(true);

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        await streamChat(
          question,
          (event: AgentEvent) => {
            if (event.type === "final") {
              const final = event.data as unknown as FinalAnswer;
              patch(assistantId, (m) => ({
                ...m,
                content: final.answer || m.content,
                final,
                steps: [...m.steps, event],
              }));
            } else if (event.type === "error") {
              patch(assistantId, (m) => ({
                ...m,
                error: event.detail || "Something went wrong.",
                steps: [...m.steps, event],
              }));
            } else {
              // agent_step
              patch(assistantId, (m) => ({ ...m, steps: [...m.steps, event] }));
            }
          },
          controller.signal,
        );
      } catch (err: any) {
        patch(assistantId, (m) => ({
          ...m,
          error: err?.message || "Failed to reach the analysis engine.",
        }));
      } finally {
        patch(assistantId, (m) => ({ ...m, streaming: false }));
        setIsStreaming(false);
        abortRef.current = null;
      }
    },
    [isStreaming, patch],
  );

  const stop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    setMessages([]);
    setIsStreaming(false);
  }, []);

  return { messages, isStreaming, ask, stop, reset };
}
