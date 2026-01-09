# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
RUN pip install --no-cache-dir uv==0.9.22

COPY . .

# Create virtual environment and install dependencies using uv
RUN uv sync && uv pip install -r ui/requirements.txt

# Create non-root user and adjust permissions
RUN useradd -m -u 1000 traffic && \
    chmod +x docker-entrypoint.sh && \
    chown -R traffic:traffic /app

# Switch to non-root user
USER traffic

# Update PATH to use venv
ENV PATH="/app/.venv/bin:$PATH"

# Expose API port and UI port
EXPOSE 8081 7860

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=10s \
    CMD curl -f http://localhost:8081/health || exit 1

# Run both API and UI services using entrypoint script
CMD ["bash", "docker-entrypoint.sh"]
