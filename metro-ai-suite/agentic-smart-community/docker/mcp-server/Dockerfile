# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
# Smart Community MCP server image. 
# 
# Build context is the repository root (see docker/compose.yaml build.context: ..).
# WORKDIR is /app so that config `evaluate_rules_path: ./demo/prompts/...` — resolved
# relative to the process cwd — points at the prompts copied in below.

# -slim, not the full node image: better-sqlite3 ships prebuilt binaries since v13,
# so no compiler is needed and the ~1.4 GB buildpack-deps toolchain buys nothing.
# Everything below is therefore an explicit dependency — slim ships none of it.
FROM node:22-trixie-slim

# Security updates first: Docker Hub's official slim images lag the Debian
# repos, so preinstalled base-layer packages (e.g. util-linux 2.41-5) can carry
# CVEs that already have fixes in trixie (e.g. 2.41.5-0+deb13u1). A plain
# rebuild without this layer keeps the stale base-layer debs forever.
RUN apt-get update -y && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Runtime deps:
#   ffmpeg          — for scene_query frame resize
#   jq              — bundled use-case registration in the entrypoint
#   python3         — evaluate_rules.py use-case overrides
#   curl            — compose healthcheck + use-case registration in the entrypoint
#   ca-certificates — HTTPS requests made by the entrypoint
#   tzdata          — zoneinfo DB so SQLite's datetime('now','localtime') and Node
#                     resolve TZ correctly; without it a set TZ falls back to UTC,
#                     writing event timestamps 8h off (see docker-compose.yaml TZ).
# dpkg-dev unpacks the FFmpeg and ca-certificates source packages for license
# compliance and is removed after npm ci.

RUN sed -Ei "s/Types: deb/Types: deb deb-src/g" /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        dpkg-dev \
        ffmpeg \
        jq \
        python3 \
        tzdata

# Default timezone. compose overrides this with the host's TZ (see set_env.sh); this
# ENV is the fallback when the image is run without one so timestamps are not UTC.
ENV TZ=Asia/Shanghai

WORKDIR /app

# Install workspace dependencies. package-lock.json is committed, so use `npm ci`.
# better-sqlite3 resolves its prebuilt binary per platform — do NOT copy the host's
# node_modules.
COPY package.json package-lock.json tsconfig.json ./
COPY packages ./packages
RUN npm ci

# Retain exact source packages for every copyleft Debian component distributed
# by the final image, with a binary-to-source version mapping for auditability.
RUN mkdir -p /copyleft_sources/deb \
    && dpkg-query -W -f='${binary:Package}\t${Version}\t${source:Package}\t${source:Version}\n' \
        | while IFS="$(printf '\t')" read -r binary_package binary_version source_package source_version; do \
            package_name="${binary_package%%:*}"; \
            if [ "$package_name" != "dpkg-dev" ] \
                && grep -Eqi 'GPL|LGPL|MPL|EPL|CDDL' "/usr/share/doc/$package_name/copyright" 2>/dev/null; then \
                printf '%s\t%s\t%s\t%s\n' "$binary_package" "$binary_version" "$source_package" "$source_version"; \
            fi; \
        done | sort -u > /copyleft_sources/deb/package-source-map.tsv \
    && cut -f3,4 /copyleft_sources/deb/package-source-map.tsv | sort -u \
        | awk -F '\t' '{print $1 "=" $2}' > /tmp/copyleft-source-requests.txt \
    && cd /copyleft_sources/deb \
    && xargs -r -n 32 apt-get source -q --download-only < /tmp/copyleft-source-requests.txt \
    && rm -f /tmp/copyleft-source-requests.txt \
    && apt-get purge -y --auto-remove dpkg-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*

# Build the workspace: dashboard (vite) + all TS packages (tsc -b) → dist/.
# Delete any stray *.tsbuildinfo first: `tsc -b` treats a buildinfo without its dist
# as "already built" and skips emit, yielding an image with no dist/index.js. Then
# assert the entrypoint file exists so a silent no-emit fails the build, not runtime.
RUN find . -name '*.tsbuildinfo' -not -path '*/node_modules/*' -delete \
    && npm run build \
    && test -f packages/mcp-server/dist/index.js \
    && npm prune --omit=dev --omit=optional \
    && rm -rf \
        /root/.npm \
        /usr/local/bin/npm \
        /usr/local/bin/npx \
        /usr/local/lib/node_modules/npm

# Task prompts + the elder_wakeup evaluate-rules adapter, resolved relative to
# WORKDIR at runtime; plus the config templates the entrypoint falls back to.
COPY demo/prompts ./demo/prompts
COPY config.yaml.example monitors.yaml.example ./

COPY docker/mcp-server/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

RUN apt-get purge -y --allow-remove-essential perl-base \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN groupmod -n appuser node \
    && usermod -l appuser -d /home/appuser -m node
USER appuser

# MCP HTTP + UI, and the events webhook (informational under network_mode: host).
EXPOSE 3100 3101

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
