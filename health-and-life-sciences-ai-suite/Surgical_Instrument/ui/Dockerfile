# Surgical Instrument — UI image.
#
# Stage 1 builds the Vite React app; stage 2 serves the static bundle via
# nginx and reverse-proxies /api → surgical-backend:5001 (see nginx.conf).

# -----------------------------
# Stage 1: build the Vite app
# -----------------------------
FROM node:20-slim AS build

WORKDIR /app

# NOTE: do NOT set NODE_ENV=production here — npm ci would skip devDependencies
# and `vite build` (a devDep) would be unavailable. `vite build` already emits
# a production bundle regardless of NODE_ENV.

# Leave VITE_API_BASE_URL unset in production — the app falls back to
# `${window.location.origin}/api` which nginx proxies to the backend.

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .
RUN npm run build

# -----------------------------
# Stage 2: serve with nginx
# -----------------------------
FROM nginx:1.27-alpine

RUN apk add --no-cache curl

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -fsS http://localhost:8080/ >/dev/null || exit 1

CMD ["nginx", "-g", "daemon off;"]
