// App — top-level layout. Chat copilot on the left, market-overview dashboard on
// the right (stacks on mobile). Dark, modern SaaS-copilot aesthetic.

import { useEffect, useState } from "react";
import { Activity, Code2, Moon, Sun } from "lucide-react";
import ChatWindow from "./components/ChatWindow";
import KpiDashboard from "./components/KpiDashboard";
import { useTheme } from "./hooks/useTheme";

function ThemeToggle() {
  const { theme, toggle } = useTheme();
  return (
    <button
      onClick={toggle}
      title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
      className="flex h-8 w-8 items-center justify-center rounded-lg border border-line text-muted transition hover:text-bright hover:border-line-strong"
    >
      {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </button>
  );
}

const BASE_URL = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

function BackendStatus() {
  const [ok, setOk] = useState<boolean | null>(null);
  useEffect(() => {
    fetch(`${BASE_URL}/health`)
      .then((r) => r.json())
      .then((j) => setOk(j.status === "ok"))
      .catch(() => setOk(false));
  }, []);
  const color = ok === null ? "bg-faint" : ok ? "bg-emerald-400" : "bg-rose-400";
  const label = ok === null ? "connecting" : ok ? "online" : "offline";
  return (
    <div className="flex items-center gap-1.5 text-[11px] text-muted">
      <span className={`h-2 w-2 rounded-full ${color} ${ok ? "animate-pulse-dot" : ""}`} />
      backend {label}
    </div>
  );
}

export default function App() {
  return (
    <div className="flex h-screen flex-col bg-page">
      {/* Top bar */}
      <header className="flex items-center justify-between border-b border-line bg-surface/50 px-4 py-2.5 backdrop-blur">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-gold-500 to-brand-600">
            <Activity className="h-4 w-4 text-bright" />
          </div>
          <div>
            <div className="text-sm font-bold text-bright">
              DubaiPulse <span className="text-accent-gold">Analyst</span>
            </div>
            <div className="text-[10px] text-faint">Agentic real-estate market intelligence</div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <BackendStatus />
          <ThemeToggle />
          <a
            href="https://github.com/krish2105/Dubai-Pulse-Analyst-"
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1.5 rounded-lg border border-line px-2.5 py-1.5 text-xs text-content hover:text-bright hover:border-line-strong"
          >
            <Code2 className="h-3.5 w-3.5" /> Source
          </a>
        </div>
      </header>

      {/* Main split */}
      <main className="flex flex-1 flex-col overflow-hidden lg:flex-row">
        <section className="flex min-h-0 flex-1 flex-col lg:border-r lg:border-line">
          <ChatWindow />
        </section>
        <aside className="hidden w-[340px] shrink-0 overflow-y-auto bg-page/60 lg:block xl:w-[380px]">
          <KpiDashboard />
        </aside>
      </main>
    </div>
  );
}
