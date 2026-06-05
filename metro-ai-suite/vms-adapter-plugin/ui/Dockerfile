# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# Multi-stage Dockerfile for VMS-UI
# Stage 1: Build the React/Vite application
FROM node:26.2.0-trixie-slim AS builder

ARG COPYLEFT_SOURCES=false

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Collect copyleft npm sources when explicitly requested.
RUN mkdir -p /copyleft_sources/npm && \
        if [ "$COPYLEFT_SOURCES" = "true" ]; then \
            node -e 'const fs=require("fs"),path=require("path"),{execSync}=require("child_process");const root="/app/node_modules",outDir="/copyleft_sources/npm",pattern=/(copyleft|gpl|lgpl|epl|mpl|cddl)/i,packed=new Set(),report=[];function collect(dir){if(!fs.existsSync(dir))return;for(const entry of fs.readdirSync(dir,{withFileTypes:true})){if(!entry.isDirectory()||entry.name.startsWith("."))continue;const full=path.join(dir,entry.name);if(entry.name.startsWith("@")){collect(full);continue;}const pkgJsonPath=path.join(full,"package.json");if(!fs.existsSync(pkgJsonPath))continue;let pkg;try{pkg=JSON.parse(fs.readFileSync(pkgJsonPath,"utf8"));}catch{continue;}const lic=typeof pkg.license==="string"?pkg.license:Array.isArray(pkg.licenses)?pkg.licenses.map((x)=>typeof x==="string"?x:(x&&x.type)||"").filter(Boolean).join(" | "):(pkg.license&&typeof pkg.license==="object"&&pkg.license.type)?String(pkg.license.type):"";if(!pkg.name||!pkg.version||!lic||!pattern.test(lic))continue;const spec=`${pkg.name}@${pkg.version}`;if(packed.has(spec))continue;packed.add(spec);report.push(`${spec} | ${lic}`);try{execSync(`npm pack ${spec} --pack-destination ${outDir}`,{stdio:"inherit"});}catch{}}}collect(root);fs.writeFileSync(path.join(outDir,"copyleft_package_list.txt"),report.join("\n")+(report.length?"\n":""));' ; \
        fi

# Copy source code
COPY . .

# Build the application
RUN npm run build

# Stage 2: Serve with nginx
FROM nginx:1.31.1-trixie

ARG COPYLEFT_SOURCES=false

# Security update for krb5 runtime libs (fixes CVE-2026-40356)
RUN apt-get update && \
    apt-get install -y --no-install-recommends --only-upgrade \
      libkrb5support0 \
      libkrb5-3 \
      libgssapi-krb5-2 \
      libk5crypto3 && \
    rm -rf /var/lib/apt/lists/*

# Copy built assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html
COPY --from=builder /copyleft_sources /copyleft_sources

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY third_party_programs.txt ./

# Run nginx as non-root user
RUN chown -R nginx:nginx /usr/share/nginx/html /var/cache/nginx /var/log/nginx /etc/nginx/conf.d && \
    touch /var/run/nginx.pid && \
    chown nginx:nginx /var/run/nginx.pid

# Optionally download Debian copyleft sources if requested.
RUN if [ "$COPYLEFT_SOURCES" = "true" ]; then \
        apt-get update && \
        apt-get install -y --no-install-recommends dpkg-dev ca-certificates >/dev/null && \
        mkdir -p /copyleft_sources/deb && \
        : > /copyleft_sources/deb/copyleft_package_list.txt && \
        : > /copyleft_sources/deb/source_fetch_errors.txt && \
        if [ -f /etc/apt/sources.list ]; then \
          sed -Ei 's/^#\s*deb-src\s+/deb-src /' /etc/apt/sources.list; \
        fi && \
        if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
          awk '/^Types:/ {$0="Types: deb-src"} {print}' /etc/apt/sources.list.d/debian.sources > /etc/apt/sources.list.d/debian-src.sources; \
        fi && \
        apt-get update && \
        cd /copyleft_sources/deb && \
        for package in $(dpkg-query -W -f='${binary:Package}\n' | sort -u); do \
            copyright_file="/usr/share/doc/${package}/copyright"; \
            [ -f "$copyright_file" ] || continue; \
            if grep -Eiq 'Copyleft|GPL|LGPL|EPL|MPL|CDDL' "$copyright_file"; then \
                license=$(sed -n 's/^License: //p' "$copyright_file" | paste -sd ' | ' -); \
                [ -n "$license" ] || license="UNKNOWN"; \
                echo "${package}|${license}" >> /copyleft_sources/deb/copyleft_package_list.txt; \
                apt-get source -q --download-only "$package" >> /copyleft_sources/deb/source_fetch_errors.txt 2>&1 || true; \
            fi; \
        done && \
        apt-get purge -y --auto-remove dpkg-dev >/dev/null && \
        rm -rf /var/lib/apt/lists/*; \
    fi


USER nginx

# Expose port 80
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -fsS http://localhost/ > /dev/null || exit 1

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
