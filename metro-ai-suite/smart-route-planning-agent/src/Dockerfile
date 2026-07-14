# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

FROM python:3.12-slim

ARG USER_ID=1000
ARG USER_GROUP_ID=1000

# Set working directory
WORKDIR /app

# Copy code into the container
RUN pip install --no-cache-dir "uv>=0.9.22,<1.0.0"
COPY . .
RUN uv sync

# Upgrade pip and install dependencies directly from pyproject.toml

# Create non-root user and change ownership
RUN groupadd -g ${USER_GROUP_ID} routeuser && \
  useradd -m -s /usr/sbin/nologin -u ${USER_ID} -g ${USER_GROUP_ID} routeuser && \
  chown -R routeuser:routeuser /app

USER routeuser

# Expose port for Gradio interface
EXPOSE 7860

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD uv run python health_check.py 7860 || exit 1

# Run the application
CMD ["uv", "run", "python", "main.py"]
