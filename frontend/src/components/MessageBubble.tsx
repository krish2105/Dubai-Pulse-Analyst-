// MessageBubble — renders a user or assistant message. Assistant messages carry
// the live reasoning trace, the markdown answer, and the source citation.

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AlertCircle, Sparkles, User } from "lucide-react";
import type { ChatMessage } from "../lib/types";
import ReasoningTracePanel from "./ReasoningTracePanel";
import SourceCitation from "./SourceCitation";

export default function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <div className="flex justify-end animate-fade-in">
        <div className="flex max-w-[85%] items-start gap-2.5">
          <div className="rounded-2xl rounded-tr-sm bg-brand-600/90 px-4 py-2.5 text-sm text-white shadow">
            {message.content}
          </div>
          <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand-600/30 text-brand-300">
            <User className="h-4 w-4" />
          </div>
        </div>
      </div>
    );
  }

  const waitingForAnswer = message.streaming && !message.content && !message.error;

  return (
    <div className="flex justify-start animate-fade-in">
      <div className="flex w-full max-w-[92%] items-start gap-2.5">
        <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gold-500/20 text-gold-400">
          <Sparkles className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          {/* Live reasoning trace (streams as steps arrive) */}
          <ReasoningTracePanel steps={message.steps} streaming={message.streaming} />

          {/* The answer */}
          {message.content && (
            <div className="prose-answer mt-3 rounded-2xl rounded-tl-sm border border-ink-600 bg-ink-800 px-4 py-3 text-sm text-slate-200">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
            </div>
          )}

          {waitingForAnswer && (
            <div className="mt-3 flex items-center gap-1.5 text-xs text-slate-500">
              <span className="h-1.5 w-1.5 rounded-full bg-slate-500 animate-pulse-dot" />
              investigating…
            </div>
          )}

          {/* Error */}
          {message.error && (
            <div className="mt-3 flex items-start gap-2 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2.5 text-sm text-rose-200">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{message.error}</span>
            </div>
          )}

          {/* Citations + confidence */}
          {message.final && <SourceCitation final={message.final} />}
        </div>
      </div>
    </div>
  );
}
