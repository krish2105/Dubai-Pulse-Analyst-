// MessageBubble — renders a user or assistant message. Assistant messages carry
// the live reasoning trace, the streamed markdown answer (with an inline chart
// and RTL support for Arabic), and the source citation.

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AlertCircle, Sparkles, User } from "lucide-react";
import type { ChatMessage } from "../lib/types";
import ReasoningTracePanel from "./ReasoningTracePanel";
import SourceCitation from "./SourceCitation";
import AnswerChart from "./AnswerChart";

export default function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  const rtl = message.language === "ar";

  if (isUser) {
    return (
      <div className="flex justify-end animate-fade-in">
        <div className="flex max-w-[85%] items-start gap-2.5">
          <div className="rounded-2xl rounded-tr-sm bg-brand-600/90 px-4 py-2.5 text-sm text-white shadow">
            {message.content}
          </div>
          <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand-600/30 text-brand-500">
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
        <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gold-500/20 text-accent-gold">
          <Sparkles className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          {/* Live reasoning trace (streams as steps arrive) */}
          <ReasoningTracePanel steps={message.steps} streaming={message.streaming} />

          {/* The streamed answer */}
          {message.content && (
            <div
              dir={rtl ? "rtl" : "ltr"}
              className="prose-answer mt-3 rounded-2xl rounded-tl-sm border border-line bg-surface px-4 py-3 text-sm text-content"
            >
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
              {message.streaming && (
                <span className="ml-0.5 inline-block h-3.5 w-[2px] translate-y-0.5 animate-blink bg-accent-gold" />
              )}
            </div>
          )}

          {waitingForAnswer && (
            <div className="mt-3 flex items-center gap-1.5 text-xs text-faint">
              <span className="h-1.5 w-1.5 rounded-full bg-faint animate-pulse-dot" />
              investigating…
            </div>
          )}

          {/* Inline chart from the analysis (only once finalised) */}
          {message.final && !message.streaming && <AnswerChart final={message.final} />}

          {/* Error */}
          {message.error && (
            <div className="mt-3 flex items-start gap-2 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2.5 text-sm text-rose-500">
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
