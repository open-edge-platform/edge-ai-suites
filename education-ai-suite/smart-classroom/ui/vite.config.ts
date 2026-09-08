import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    // video.js and its streaming parsers are statically imported and total
    // ~700 kB; splitting them further breaks their CJS interop cycles.
    chunkSizeWarningLimit: 750,
    rolldownOptions: {
      output: {
        // Whole packages only. Size-based splitting cuts through CJS interop
        // cycles, which then run before the defining chunk has evaluated.
        codeSplitting: {
          groups: [
            {
              name: 'react-vendor',
              test: /node_modules[\\/](react|react-dom|scheduler)[\\/]/,
              priority: 30,
            },
            {
              name: 'video-vendor',
              test: /node_modules[\\/](video\.js|@videojs|m3u8-parser|mpd-parser|mux\.js|aes-decrypter)[\\/]/,
              priority: 20,
            },
            {
              // pdfjs is deliberately ungrouped: it is only reached through a
              // dynamic import, and any group would make it load eagerly.
              name: 'vendor',
              test: /node_modules[\\/](?!pdfjs-dist[\\/])/,
              priority: 10,
            },
          ],
        },
      },
    },
  },
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
