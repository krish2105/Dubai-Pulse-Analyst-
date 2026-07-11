// ChatWindow — the core chat interface: message list, input box, example prompts,
// and auto-scroll. Delegates streaming to useAgentStream.

import { useEffect, useRef, useState } from "react";
import { SendHorizontal, Square, Sparkles, RotateCcw } from "lucide-react";
import { useAgentStream } from "../hooks/useAgentStream";
import MessageBubble from "./MessageBubble";

const EXAMPLES = [
  "Which zones saw the biggest price increase in 2024?",
  "Compare rental yields across Downtown Dubai and Dubai Marina in 2025.",
  "Why did off-plan transaction volume change in early 2022?",
  "What is the average price per sqft in Palm Jumeirah for secondary sales in 2025?",
  "How did the CBUAE base rate relate to secondary price growth from 2022 to 2024?",
];

export default function ChatWindow() {
  const { messages, isStreaming, ask, stop, reset } = useAgentStream();
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const submit = (q?: string) => {
    const question = (q ?? input).trim();
    if (!question || isStreaming) return;
    setInput("");
    ask(question);
  };

  const empty = messages.length === 0;

  return (
    <div className="flex h-full flex-col">
      {/* Header row */}
      <div className="flex items-center justify-between border-b border-ink-700 px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gold-500/20 text-gold-400">
            <Sparkles className="h-4 w-4" />
          </div>
          <div>
            <div className="text-sm font-semibold text-white">Analyst Copilot</div>
            <div className="text-[11px] text-slate-500">Multi-agent · grounded · verified</div>
          </div>
        </div>
        {!empty && (
          <button
            onClick={reset}
            className="flex items-center gap-1.5 rounded-lg border border-ink-600 px-2.5 py-1.5 text-xs text-slate-400 hover:text-white hover:border-ink-500"
          >
            <RotateCcw className="h-3.5 w-3.5" /> New chat
          </button>
        )}
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 space-y-5 overflow-y-auto px-4 py-5">
        {empty ? (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <div className="mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-gold-500/30 to-brand-600/30 text-gold-400">
              <Sparkles className="h-7 w-7" />
            </div>
            <h2 className="text-lg font-semibold text-white">Investigate the Dubai property market</h2>
            <p className="mt-1 max-w-md text-sm text-slate-400">
              Ask about price trends, rental yields, off-plan volumes or what drove a move.
              Every answer is grounded in the data and checked by a verifier.
            </p>
            <div className="mt-5 flex max-w-lg flex-wrap justify-center gap-2">
              {EXAMPLES.map((ex) => (
                <button
                  key={ex}
                  onClick={() => submit(ex)}
                  className="rounded-full border border-ink-600 bg-ink-800 px-3 py-1.5 text-xs text-slate-300 transition hover:border-brand-500 hover:text-white"
                >
                  {ex}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((m) => <MessageBubble key={m.id} message={m} />)
        )}
      </div>

      {/* Input */}
      <div className="border-t border-ink-700 p-3">
        <div className="flex items-end gap-2 rounded-xl border border-ink-600 bg-ink-800 px-3 py-2 focus-within:border-brand-500">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            rows={1}
            placeholder="Ask about Dubai real estate…  (Enter to send)"
            className="max-h-32 flex-1 resize-none bg-transparent text-sm text-slate-200 placeholder-slate-500 outline-none"
          />
          {isStreaming ? (
            <button
              onClick={stop}
              className="flex h-8 w-8 items-center justify-center rounded-lg bg-rose-500/20 text-rose-300 hover:bg-rose-500/30"
              title="Stop"
            >
              <Square className="h-4 w-4" />
            </button>
          ) : (
            <button
              onClick={() => submit()}
              disabled={!input.trim()}
              className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-white transition hover:bg-brand-500 disabled:opacity-40"
              title="Send"
            >
              <SendHorizontal className="h-4 w-4" />
            </button>
          )}
        </div>
        <p className="mt-1.5 px-1 text-[10px] text-slate-600">
          DubaiPulse can make mistakes — figures are verified against source data, but always confirm before acting.
        </p>
      </div>
    </div>
  );
}
