import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Dev server proxies /api, /events, /video, /frame to the backend so
// the React app behaves identically in dev and in the nginx-fronted prod build.
const BACKEND = process.env.VITE_BACKEND_URL ?? 'http://localhost:5001';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api':    { target: BACKEND, changeOrigin: true },
      '/events': { target: BACKEND, changeOrigin: true, ws: false },
      '/video':  { target: BACKEND, changeOrigin: true },
      '/frame':  { target: BACKEND, changeOrigin: true },
      '/health': { target: BACKEND, changeOrigin: true },
      '/status': { target: BACKEND, changeOrigin: true },
      '/start':  { target: BACKEND, changeOrigin: true },
      '/stop':   { target: BACKEND, changeOrigin: true },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
    target: 'es2022',
  },
});
