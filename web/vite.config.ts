import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// In development and `vite preview`, `/api` is proxied to the FastAPI service, so the
// browser sees one origin and no CORS is involved. Production builds call
// `VITE_API_BASE_URL` directly.
const apiTarget = process.env.VITE_DEV_API_TARGET ?? "http://127.0.0.1:8000";
const proxy = { "/api": { target: apiTarget, changeOrigin: true } };

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy },
  preview: { port: 4173, proxy },
  build: { sourcemap: true },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    css: false,
  },
});
