import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Dev proxy keeps the browser same-origin with the API so httpOnly cookies and their paths work unchanged.
const api = "http://localhost:8000";
const paths = ["/auth", "/me", "/patients", "/tasks", "/summaries", "/providers", "/locations", "/review", "/hubs", "/invites", "/admin-api", "/meta", "/health"];

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173, proxy: Object.fromEntries(paths.map((p) => [p, { target: api, changeOrigin: true }])) },
});
