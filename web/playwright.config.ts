import path from "node:path";

import { defineConfig, devices } from "@playwright/test";

// End-to-end runs against the real FastAPI service with models off, so it needs no
// network and burns no quota. The web app is built and served by `vite preview`,
// which proxies /api to that service. Set E2E_BASE_URL to test a deployed frontend
// instead; then no local servers start.
const API_PORT = Number(process.env.E2E_API_PORT ?? 8787);
const WEB_PORT = Number(process.env.E2E_WEB_PORT ?? 4174);
const OUT_DIR = path.resolve(import.meta.dirname, "test-results", "e2e-out");
const external = process.env.E2E_BASE_URL;

export default defineConfig({
  testDir: "e2e",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  timeout: 30_000,
  use: {
    baseURL: external ?? `http://127.0.0.1:${WEB_PORT}`,
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 1000 } } }],
  webServer: external
    ? undefined
    : [
        {
          command: `uv run uvicorn support_reply.api.app:app --host 127.0.0.1 --port ${API_PORT}`,
          cwd: "..",
          url: `http://127.0.0.1:${API_PORT}/api/health`,
          reuseExistingServer: false,
          timeout: 60_000,
          env: {
            REPLY_DESK_MODELS: "off",
            REPLY_DESK_OUT_DIR: OUT_DIR,
            REPLY_DESK_RATE_PER_MINUTE: "1000",
            REPLY_DESK_ENV: "e2e",
            LOG_LEVEL: "WARNING",
            // Present but empty, so a developer's .env cannot switch the gate on here.
            ACCESS_CODE: "",
          },
        },
        {
          command: `npm run build && npx vite preview --host 127.0.0.1 --port ${WEB_PORT} --strictPort`,
          url: `http://127.0.0.1:${WEB_PORT}`,
          reuseExistingServer: false,
          timeout: 120_000,
          env: { VITE_DEV_API_TARGET: `http://127.0.0.1:${API_PORT}` },
        },
      ],
});
