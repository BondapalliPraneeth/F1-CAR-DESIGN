/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#07080c",
        panel: "#0e1016",
        panel2: "#161921",
        line: "#262a35",
        ink: { DEFAULT: "#eceef2", 2: "#a9afbc", 3: "#717887" },
        accent: { DEFAULT: "#ef3b2d", strong: "#c92a1f" },
        sev: { healthy: "#22c55e", minor: "#facc15", moderate: "#f59e0b", severe: "#f97316", critical: "#ef4444" },
      },
      fontFamily: { sans: ["Inter", "system-ui", "sans-serif"], mono: ["JetBrains Mono", "ui-monospace", "monospace"] },
    },
  },
  plugins: [],
};
