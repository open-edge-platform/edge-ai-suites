# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

FROM python:3.12-slim AS base

# Install system dependencies needed for building, upgrade to apply security patches
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends curl \
    && python -m pip install --upgrade --no-cache-dir pip \
    && rm -rf /var/lib/apt/lists/*

# Build stage
FROM base AS builder

# Install uv
RUN pip install --no-cache-dir uv==0.11.10

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies to a virtual environment
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV UV_PROJECT_ENVIRONMENT="/opt/venv"
RUN uv sync --frozen --no-dev --no-install-project

# Download Chart.js during build for airgapped runtime
RUN mkdir -p ui/js/vendor && \
    curl -o ui/js/vendor/chart.js https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js

# Production stage
FROM base AS production

RUN apt-get update && apt-get upgrade -y && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/opt/venv/bin:$PATH"

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Set working directory and change ownership
WORKDIR /app

# Copy application code
COPY --chown=appuser:appuser main.py ./
COPY --chown=appuser:appuser backend ./backend
COPY --chown=appuser:appuser ui ./ui

# Copy Chart.js from builder stage
COPY --from=builder --chown=appuser:appuser /app/ui/js/vendor/chart.js ./ui/js/vendor/chart.js

# Optionally download copyleft sources if requested
ARG COPYLEFT_SOURCES=false
RUN if [ "$COPYLEFT_SOURCES" = "true" ]; then \
    apt-get update && \
    # Get list of installed deb packages with copyleft licenses \
    sed -Ei 's/# deb-src /deb-src /' /etc/apt/sources.list && \
    apt-get update && \
    mkdir -p /copyleft_sources/deb && cd /copyleft_sources/deb && \
    echo -n $null > copyleft_package_list.txt && \
    for package in $(dpkg -l | awk '/^ii/ {print $2}' | cut -d: -f1); do \
    grep -l 'Copyleft\|GPL\|LGPL\|EPL\|MPL\|CDDL' /usr/share/doc/${package}/copyright; \
    exit_status=$?; \
    if [ $exit_status -eq 0 ]; then \
    echo $package >> copyleft_package_list.txt; \
    apt-get source -q --download-only $package; \
    fi; \
    done; \
    # Get source code for installed Python packages with copyleft licenses \
    mkdir -p /copyleft_sources/python && \
    cd /copyleft_sources/python && \
    apt-get update && apt-get install -y gcc build-essential libffi-dev python3-dev && \
    # Download python package sources with relevant licenses \
    pip3 freeze | cut -d= -f1 | while read pkg; do \
    meta=$(pip3 show $pkg 2>/dev/null); \
    lic=$(echo "$meta" | grep -i '^License:' | grep -E 'MPL|GPL|General Public License|EPL|Eclipse Public License|CDDL|LGPL'); \
    if [ ! -z "$lic" ]; then \
    echo "Downloading source for $pkg with license: $lic"; \
    pip3 download --no-binary :all: $pkg || true; \
    fi; \
    done; \
    apt-get remove --purge -y gcc build-essential libffi-dev python3-dev; \
    fi

# Switch to non-root user
USER appuser

EXPOSE 4173

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "4173"]
