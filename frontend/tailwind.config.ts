import type { Config } from "tailwindcss";

// Semantic colors are backed by CSS variables (see src/styles/index.css) so the
// SAME class names theme both light and dark. Accent scales (brand/gold/…) are
// static and used on low-opacity chips that read on either theme.
const v = (name: string) => `rgb(var(${name}) / <alpha-value>)`;

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // --- semantic (theme-aware) ---
        page: v("--page"),
        surface: v("--surface"),
        surface2: v("--surface-2"),
        elevated: v("--elevated"),
        line: v("--line"),
        "line-strong": v("--line-strong"),
        content: v("--content"),
        muted: v("--muted"),
        faint: v("--faint"),
        bright: v("--bright"),
        // --- accents (static) ---
        brand: {
          50: "#f2f7ff", 100: "#e6f0ff", 400: "#5b9bff",
          500: "#2f7bff", 600: "#1f5fe0", 700: "#1a4bb0",
        },
        gold: { 400: "#f5c451", 500: "#e0a92e", 600: "#c78f1a" },
        ink: {
          900: "#0a0e1a", 800: "#0f1524", 700: "#161d30",
          600: "#1e263c", 500: "#2a3450",
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      keyframes: {
        "pulse-dot": { "0%, 100%": { opacity: "1" }, "50%": { opacity: "0.3" } },
        "fade-in": {
          "0%": { opacity: "0", transform: "translateY(4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "blink": { "0%, 100%": { opacity: "1" }, "50%": { opacity: "0" } },
      },
      animation: {
        "pulse-dot": "pulse-dot 1.2s ease-in-out infinite",
        "fade-in": "fade-in 0.25s ease-out",
        "blink": "blink 1s step-end infinite",
      },
    },
  },
  plugins: [],
} satisfies Config;
