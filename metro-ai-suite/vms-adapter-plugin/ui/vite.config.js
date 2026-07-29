// Copyright (C) 2025 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

const API_BASE      = process.env.VITE_API_BASE       || 'http://localhost:8085';
const MEDIAMTX_BASE = process.env.VITE_MEDIAMTX_BASE  || 'http://localhost:8889';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    proxy: {
      '/v1': {
        target: API_BASE,
        changeOrigin: true,
        secure: false,
      },
      // Proxy MediaMTX WebRTC/WHEP calls to avoid CORS issues.
      // /whep/{slug}/whep  →  http://mediamtx:8889/{slug}/whep
      '/whep': {
        target: MEDIAMTX_BASE,
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path.replace(/^\/whep/, ''),
      },
    },
  },
})
