# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

FROM python:3.12-slim AS base

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN groupadd -g 1000 appuser && useradd -u 1000 -g appuser -m appuser

WORKDIR /app

COPY pyproject.toml ./
COPY plugin ./plugin
COPY vms_shim ./vms_shim
COPY analytics_app_shim ./analytics_app_shim
COPY third_party_programs.txt ./

RUN uv pip install --system --no-cache -e . && \
    chown -R appuser:appuser /app

# Optionally download copyleft sources if requested
ARG COPYLEFT_SOURCES=false
RUN if [ "$COPYLEFT_SOURCES" = "true" ]; then \
        export DEBIAN_FRONTEND=noninteractive && \
        apt-get update && \
        apt-get install -y --no-install-recommends dpkg-dev ca-certificates gcc build-essential libffi-dev python3-dev >/dev/null && \
        mkdir -p /copyleft_sources/deb /copyleft_sources/python && \
        : > /copyleft_sources/deb/copyleft_package_list.txt && \
        : > /copyleft_sources/deb/source_fetch_errors.txt && \
        : > /copyleft_sources/python/copyleft_package_list.txt && \
        : > /copyleft_sources/python/source_fetch_errors.txt && \
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
        cd /copyleft_sources/python && \
        pip3 freeze | cut -d= -f1 | while read -r pkg; do \
            [ -n "$pkg" ] || continue; \
            meta=$(pip3 show "$pkg" 2>/dev/null || true); \
            lic=$(echo "$meta" | grep -i '^License:' | grep -E 'MPL|GPL|General Public License|EPL|Eclipse Public License|CDDL|LGPL' || true); \
            if [ -n "$lic" ]; then \
                echo "${pkg}|${lic#License: }" >> /copyleft_sources/python/copyleft_package_list.txt; \
                pip3 download --no-binary :all: "$pkg" >> /copyleft_sources/python/source_fetch_errors.txt 2>&1 || true; \
            fi; \
        done && \
        apt-get purge -y --auto-remove dpkg-dev gcc build-essential libffi-dev python3-dev >/dev/null && \
        rm -rf /var/lib/apt/lists/*; \
    fi

USER appuser

EXPOSE 8080

ENTRYPOINT ["uvicorn", "plugin.core.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
