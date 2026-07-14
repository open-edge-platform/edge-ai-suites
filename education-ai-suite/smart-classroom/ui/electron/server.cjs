// Embedded static + proxy micro-server for the packaged Electron app.
//
// Mirrors the Vite dev proxy (see ui/vite.config.ts): the built SPA in `dist/`
// is served over a local origin, and `/api/v1` requests are proxied to the
// content-search backend on port 9011. Serving the UI same-origin with that
// proxy is what lets the content-search backend (which has no CORS) be reached
// from Electron without any backend changes. Main-backend calls (port 8000) go
// cross-origin straight from the UI and rely on its `allow_origins=["*"]`.

const path = require('path');
const express = require('express');
const { createProxyMiddleware } = require('http-proxy-middleware');

const CONTENT_SEARCH_TARGET =
  process.env.CONTENT_SEARCH_TARGET || 'http://127.0.0.1:9011';

/**
 * Start the static + proxy server bound to loopback on an ephemeral port.
 * @param {string} distPath Absolute path to the built `dist/` directory.
 * @returns {Promise<{port: number, close: () => void}>}
 */
function startServer(distPath) {
  const app = express();

  // Proxy /api/v1 -> content-search backend. Registered before any body
  // parser and matched by full path (pathFilter) so multipart uploads and
  // streamed file downloads pass through untouched. 1:1 with the Vite proxy.
  app.use(
    createProxyMiddleware({
      pathFilter: '/api/v1',
      target: CONTENT_SEARCH_TARGET,
      changeOrigin: true,
    })
  );

  // Static assets from the Vite build output.
  app.use(express.static(distPath));

  // SPA fallback: serve index.html for any other GET (deep links / refresh).
  app.use((req, res, next) => {
    if (req.method !== 'GET') return next();
    res.sendFile(path.join(distPath, 'index.html'));
  });

  return new Promise((resolve, reject) => {
    const server = app.listen(0, '127.0.0.1', () => {
      const { port } = server.address();
      resolve({ port, close: () => server.close() });
    });
    server.on('error', reject);
  });
}

module.exports = { startServer };
