# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# Dockerfile — kiosk-core / kiosk-ui
#
# Default CMD starts the kiosk-core FastAPI service on port 8012.
# The kiosk-ui service in docker-compose.yml overrides CMD to run gradio_app.py.
FROM python:3.11-slim

ARG APP_UID=1000
ARG APP_GID=1000

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# libportaudio2 is required by the sounddevice wheel at import time even
# when no mic device is used (Gradio file-upload mode).
RUN apt-get update \
    && apt-get install -y --no-install-recommends libportaudio2 curl \
    && groupadd --gid ${APP_GID} appuser \
    && useradd --uid ${APP_UID} --gid ${APP_GID} --create-home --home-dir /app appuser \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt

RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY . .

RUN mkdir -p /app/generated_audio \
    && chown -R ${APP_UID}:${APP_GID} /app

USER appuser

EXPOSE 8012

CMD ["python3", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8012"]
