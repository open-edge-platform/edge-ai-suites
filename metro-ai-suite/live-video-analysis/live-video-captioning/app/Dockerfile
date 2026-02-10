# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

FROM python:3.13-slim@sha256:49b618b8afc2742b94fa8419d8f4d3b337f111a0527d417a1db97d4683cb71a6 AS base

# Build stage
FROM base AS builder

# Install system dependencies needed for building
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install --no-cache-dir uv==0.4.23

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

RUN apt-get update && apt-get install -y --no-install-recommends curl && \
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

# Switch to non-root user
USER appuser

EXPOSE 4173

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "4173"]
