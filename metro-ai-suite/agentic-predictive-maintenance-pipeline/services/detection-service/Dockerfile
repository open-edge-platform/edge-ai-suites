# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

FROM python:3.12-slim

LABEL org.opencontainers.image.title="APM Detection Service"
LABEL org.opencontainers.image.description="Detection-layer orchestration (DL Streamer) for agentic predictive maintenance"
LABEL org.opencontainers.image.vendor="Intel Corporation"

WORKDIR /app

RUN groupadd -r appuser && useradd -r -g appuser -u 1002 appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

RUN mkdir -p /app/videos && chown -R appuser:appuser /app

USER appuser

EXPOSE 5004

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "5004", "--workers", "1"]
