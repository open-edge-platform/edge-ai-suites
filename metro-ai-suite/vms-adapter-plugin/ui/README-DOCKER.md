# VMS-UI Docker Setup

## Overview

The VMS-UI frontend is containerized using Docker with nginx serving the production-optimized React build.
The UI is designed to run as part of the `vms-adapter` Docker Compose stack defined in the parent directory.

## Quick Start

```bash
# From the vms-adapter-plugin root (parent of this directory)
cd metro-ai-suite/vms-adapter-plugin

# Copy and configure environment
cp .env.example .env
# Edit .env as needed (see Environment Variables below)

# Build and start all services (postgres, backend, ui)
docker compose up -d

# Access the UI (default port 3100)
open http://localhost:3100
```

## Docker Configuration

### Dockerfile

Multi-stage build:
- **Stage 1 (builder)**: Node.js 22-alpine, runs `npm ci` and `npm run build`
- **Stage 2 (serve)**: nginx:alpine, serves static files from `/usr/share/nginx/html`

**Image Size**: ~63 MB (highly optimized)

### Nginx Configuration

All routing is handled by `nginx.conf` inside the container:

- **Static Assets**: Served from `/usr/share/nginx/html`
- **API Proxy**: `/v1/*` → `http://backend:8080` (Docker Compose service DNS)
- **WHEP Proxy**: `/whep/*` → `http://host.docker.internal:8889` (MediaMTX on the host)
- **SSE Proxy**: `/v1/analytics-apps/*/results/stream` → `http://backend:8080` (buffering disabled)
- **SPA Routing**: All non-file routes serve `index.html`
- **Caching**: 1 year for static assets, no-cache for HTML
- **Security Headers**: X-Frame-Options, X-Content-Type-Options, X-XSS-Protection
- **Health Check**: `/health` endpoint returns `200 healthy`

### Port Configuration

- **Container Port**: 80 (nginx default)
- **Host Port**: `UI_PORT` env var (default: `3100`)

## Usage

### Using Docker Compose (recommended)

```bash
# From vms-adapter/
docker compose up -d

# Stop
docker compose down

# Full clean restart (wipes DB volume)
docker compose down -v && docker compose up -d

# View UI logs
docker compose logs -f ui

# Check health
curl http://localhost:3100/health
```

### Standalone docker run

If you need to run the UI container independently (outside of the Compose stack),
the nginx `/v1/` proxy target must be reachable. The easiest way is to override
`nginx.conf` or use a custom build that points at your backend:

```bash
docker build -t vms-adapter-ui ./ui

docker run -d \
  --name vms-adapter-ui \
  -p 3100:80 \
  --add-host=host.docker.internal:host-gateway \
  vms-adapter-ui
```

> **Note**: In standalone mode nginx will still proxy `/v1/` to `http://backend:8080`,
> which requires a Docker network containing a container named `backend`.
> For a truly standalone run you would need to rebuild with a customised nginx.conf.

## Environment Variables

Configure via `vms-adapter/.env` (see `.env.example`):

| Variable | Default | Description |
|---|---|---|
| `UI_PORT` | `3100` | Host port the UI is exposed on |
| `VITE_MEDIAMTX_BASE` | *(unset — falls back to `window.location.hostname:8889`)* | Browser-reachable MediaMTX base URL for the iframe player |

The nginx backend proxy target (`http://backend:8080`) is resolved via Docker Compose
service DNS and is **not** configurable at runtime without rebuilding the image.

## Connecting to Backend

In the Docker Compose stack the UI container reaches the backend over the internal
`vms-net` network using the service name `backend` (port 8080). This is hardcoded
in `nginx.conf`.

**No `--add-host` or `host.docker.internal` is needed for the `/v1/` proxy** — that
is only used for the `/whep/` MediaMTX proxy.

## Testing

```bash
# Health check
curl http://localhost:3100/health
# Expected: healthy

# UI is serving
curl -s -o /dev/null -w "%{http_code}" http://localhost:3100/
# Expected: 200

# API proxy (cameras)
curl http://localhost:3100/v1/cameras
# Expected: JSON array
```

## Troubleshooting

### Port Already in Use

Set `UI_PORT` in `.env` to a free port, then `docker compose up -d`.

### API Proxy Not Working

1. Check backend is running: `docker compose ps`
2. Check backend logs: `docker compose logs backend`
3. Check nginx logs: `docker compose logs ui`
4. Verify service DNS: `docker exec vms-adapter-ui wget -qO- http://backend:8080/v1/cameras`

### Container Fails to Start

1. Check logs: `docker compose logs ui`
2. Verify image built: `docker images vms-adapter-ui`
3. Check for port conflicts: `ss -tlnp | grep 3100`

## Production Deployment

1. **Build with specific tag**:
   ```bash
   docker compose build ui
   docker tag vms-adapter-ui vms-adapter-ui:v1.0.0
   ```

2. **Use Docker Compose** (already configured):
   - `vms-adapter/docker-compose.yml` defines all services with restart policies
   - Adjust `UI_PORT`, `BACKEND_PORT` in `.env` as needed

3. **Health checks**: The container has a built-in healthcheck on `/health`.

## Files

| File | Purpose |
|---|---|
| `Dockerfile` | Multi-stage build (Node builder → nginx:alpine) |
| `nginx.conf` | nginx routing: static assets, `/v1/` API proxy, `/whep/` MediaMTX proxy, SPA fallback |
| `.dockerignore` | Build context optimisation |
| `.env.example` | UI environment variable template |
| `../docker-compose.yml` | Full stack Compose definition (postgres + backend + ui) |

