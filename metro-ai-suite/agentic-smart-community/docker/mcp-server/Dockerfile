# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# Smart Community MCP server image. Runs the same Node process that
# scripts/mcp-server/start.sh launches on the host (Streamable-HTTP on :3100 +
# events webhook on :3101), but as a container joined to the rest of the stack.
#
# Build context is the repository root (see docker/compose.yaml build.context: ..).
# WORKDIR is /app so that config `evaluate_rules_path: ./demo/prompts/...` — resolved
# relative to the process cwd — points at the prompts copied in below.

FROM node:22-bookworm

# Runtime deps:
#   ffmpeg          — scene_query frame resize (see scripts/mcp-server/start.sh)
#   jq              — bundled use-case registration in the entrypoint
#   python3         — evaluate_rules.py use-case overrides
#   ca-certificates — HTTPS requests made by the entrypoint
#   tzdata          — zoneinfo DB so SQLite's datetime('now','localtime') and Node
#                     resolve TZ correctly; without it a set TZ falls back to UTC,
#                     writing event timestamps 8h off (see docker-compose.yaml TZ).
# Build deps are removed after npm ci: make/g++ build better-sqlite3 and dpkg-dev
# unpacks the corresponding FFmpeg and ca-certificates source packages for license
# compliance.
RUN sed -Ei "s/Types: deb/Types: deb deb-src/g" /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        dpkg-dev \
        ffmpeg \
        g++ \
        jq \
        make \
        python3 \
        tzdata \
    && mkdir -p /copyleft_sources/deb \
    && cd /copyleft_sources/deb \
    && apt-get source -q ca-certificates ffmpeg

# Default timezone. compose overrides this with the host's TZ (see set_env.sh); this
# ENV is the fallback when the image is run without one so timestamps are not UTC.
ENV TZ=Asia/Shanghai

WORKDIR /app

# Install workspace dependencies. package-lock.json is committed, so use `npm ci`.
# The better-sqlite3 install script compiles/downloads its native binary here — do
# NOT copy the host's node_modules (it is built for the host toolchain).
COPY package.json package-lock.json tsconfig.json ./
COPY packages ./packages
RUN npm ci \
    && apt-get purge -y --auto-remove dpkg-dev g++ make \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*

# Build the workspace: dashboard (vite) + all TS packages (tsc -b) → dist/.
# Delete any stray *.tsbuildinfo first: `tsc -b` treats a buildinfo without its dist
# as "already built" and skips emit, yielding an image with no dist/index.js. Then
# assert the entrypoint file exists so a silent no-emit fails the build, not runtime.
RUN find . -name '*.tsbuildinfo' -not -path '*/node_modules/*' -delete \
    && npm run build \
    && test -f packages/mcp-server/dist/index.js

# Task prompts + the elder_wakeup evaluate-rules adapter, resolved relative to
# WORKDIR at runtime; plus the config templates the entrypoint falls back to.
COPY demo/prompts ./demo/prompts
COPY config.yaml.example monitors.yaml.example ./

COPY docker/mcp-server/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# MCP HTTP + UI, and the events webhook (informational under network_mode: host).
EXPOSE 3100 3101

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
