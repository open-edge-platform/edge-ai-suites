// Copyright (C) 2025 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import vue from "@vitejs/plugin-vue";
import path, { resolve } from "path";
import AutoImport from "unplugin-auto-import/vite";
import { AntDesignVueResolver } from "unplugin-vue-components/resolvers";
import Components from "unplugin-vue-components/vite";
import { defineConfig, loadEnv } from "vite";
import viteCompression from "vite-plugin-compression";

const pathResolve = (dir: string) => {
  return resolve(__dirname, ".", dir);
};

const alias: Record<string, string> = {
  "@": pathResolve("./src/"),
  "vue-i18n": "vue-i18n/dist/vue-i18n.cjs.js",
};

const viteConfig = defineConfig(({ mode }) => {
  // Dev-only: read solely by the dev server's /api proxy below. Target defaults to
  // the mcp-server backend on :3100; override with SERVER_HOST / VITE_DEV_SMART_COMMUNITY_API_TARGET.
  const env = loadEnv(mode, process.cwd(), "");
  const serverHost = process.env.SERVER_HOST || env.SERVER_HOST || "127.0.0.1";
  const smartCommunity =
    process.env.VITE_DEV_SMART_COMMUNITY_API_TARGET ||
    env.VITE_DEV_SMART_COMMUNITY_API_TARGET ||
    `http://${serverHost}:3100`;
  return {
    plugins: [
      vue(),
      viteCompression(),
      AutoImport({
        imports: ["vue", "vue-router", "pinia"],
        dts: "src/auto-imports.d.ts",
        resolvers: [AntDesignVueResolver()],
      }),
      Components({
        resolvers: [
          AntDesignVueResolver({
            importStyle: false, // css in js
          }),
        ],
      }),
    ],
    root: process.cwd(),
    resolve: { alias },
    // Dev server — TEMPORARY, for frontend development only (HMR / hot reload via `npm run dev`).
    // It runs on its OWN port (8100), NOT the product port. It proxies /api to the real
    // mcp-server backend on :3100. The shipped UI is always `vite build` → dist/ hosted by
    // mcp-server on :3100 — do NOT treat :8100 as the product entry point.
    server: {
      // Loopback: this dev server proxies to an unauthenticated backend, so it
      // stays local unless you deliberately widen it (`vite --host <addr>`).
      host: "127.0.0.1",
      port: 8100,
      hmr: true,
      proxy: {
        // Forward API + websocket calls to the mcp-server backend on :3100.
        "/api": {
          target: smartCommunity,
          changeOrigin: true,
          ws: true,
        },
      },
    },
    build: {
      outDir: "dist",
      chunkSizeWarningLimit: 1500,
      rollupOptions: {
        output: {
          chunkFileNames: "assets/js/[name]-[hash].js",
          entryFileNames: "assets/js/[name]-[hash].js",
          assetFileNames: "assets/[ext]/[name]-[hash].[ext]",
        },
      },
    },
    css: {
      preprocessorOptions: {
        less: {
          javascriptEnabled: true,
          additionalData: `@import "${path.resolve(__dirname, "src/theme/index.less")}";`,
        },
      },
    },
  };
});

export default viteConfig;
