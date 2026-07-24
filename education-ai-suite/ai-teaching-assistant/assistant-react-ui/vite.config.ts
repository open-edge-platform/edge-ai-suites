import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// During `npm run dev`, proxy /api to the same backends the production
// SPA server proxies to, so dev and prod behave identically.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api/kiosk": { target: "http://127.0.0.1:8012", changeOrigin: true, rewrite: (p) => p.replace(/^\/api\/kiosk/, "") },
      "/api/rag": { target: "http://127.0.0.1:8020", changeOrigin: true, rewrite: (p) => p.replace(/^\/api\/rag/, "") },
      "/api/tts": { target: "http://127.0.0.1:8011", changeOrigin: true, rewrite: (p) => p.replace(/^\/api\/tts/, "") },
      "/api/analyzer": { target: "http://127.0.0.1:8010", changeOrigin: true, rewrite: (p) => p.replace(/^\/api\/analyzer/, "") },
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
