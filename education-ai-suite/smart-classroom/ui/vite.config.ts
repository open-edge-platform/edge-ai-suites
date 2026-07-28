import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Proxy all /api/v1 requests to the content-search backend (avoids CORS)
      '/api/v1': {
        target: 'http://127.0.0.1:9011',
        changeOrigin: true,
      },
      // Proxy /grading-api requests to the grading backend (9012). Distinct
      // prefix because /api/v1 is already claimed by content-search.
      '/grading-api': {
        target: 'http://127.0.0.1:9012',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/grading-api/, '/api/v1'),
      },
    },
  },
})
