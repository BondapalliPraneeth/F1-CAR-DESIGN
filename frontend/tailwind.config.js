/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#090d14",
        panel: "#0f1520",
        panel2: "#151d2b",
        line: "#232e40",
        ink: { DEFAULT: "#e6ebf2", 2: "#a3b0c2", 3: "#6b7a90" },
        accent: { DEFAULT: "#16c7bd", strong: "#0fa39b" },
        sev: { healthy: "#22c55e", minor: "#facc15", moderate: "#f59e0b", severe: "#f97316", critical: "#ef4444" },
      },
      fontFamily: { sans: ["Inter", "system-ui", "sans-serif"], mono: ["JetBrains Mono", "ui-monospace", "monospace"] },
    },
  },
  plugins: [],
};
