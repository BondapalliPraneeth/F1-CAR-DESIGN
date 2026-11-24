import { defineConfig, devices } from "@playwright/test";

/**
 * E2E tests run the real backend (FastAPI, SQLite fallback, offline AI) and the Vite dev server.
 * Set E2E_NO_SERVERS=1 to test against already-running servers.
 */
const backendCmd = process.platform === "win32" ? ".venv\\Scripts\\python.exe -m uvicorn app.main:app --port 8000" : "python -m uvicorn app.main:app --port 8000";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:5173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    viewport: { width: 1600, height: 1000 },
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1600, height: 1000 }, launchOptions: { args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"] } },
    },
  ],
  webServer: process.env.E2E_NO_SERVERS
    ? undefined
    : [
        {
          command: backendCmd,
          cwd: "../backend",
          url: "http://localhost:8000/health",
          reuseExistingServer: !process.env.CI,
          timeout: 120_000,
          env: { AI_PROVIDER: "offline", DATABASE_URL: "sqlite:///./e2e.db", PYTHONPATH: "." },
        },
        {
          command: "npx vite --port 5173 --strictPort",
          url: "http://localhost:5173",
          reuseExistingServer: !process.env.CI,
          timeout: 120_000,
        },
      ],
});
