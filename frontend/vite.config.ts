/// <reference types="vitest" />
import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const backend = process.env.VITE_DEV_BACKEND ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  server: { port: 5173, proxy: { "/api": backend, "/health": backend } },
  preview: { port: 4173, proxy: { "/api": backend, "/health": backend } },
  build: {
    chunkSizeWarningLimit: 5000,
    rollupOptions: {
      output: {
        manualChunks: {
          three: ["three", "@react-three/fiber", "@react-three/drei"],
          plotly: ["plotly.js-dist-min"],
        },
      },
    },
  },
  test: { include: ["src/**/*.test.ts"], environment: "node" },
});
