# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
FROM intel/dlstreamer:2026.1.0-ubuntu24

ARG APP_UID=1000
ARG APP_GID=1000

USER root

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    HF_HOME=/app/rag-service/.cache/huggingface

WORKDIR /app/rag-service

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3-venv \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt

RUN python3 -m venv "$VIRTUAL_ENV" \
    && "$VIRTUAL_ENV/bin/pip" install --upgrade pip \
    && "$VIRTUAL_ENV/bin/pip" install -r requirements.txt

COPY . .

RUN mkdir -p /app/rag-service/models \
    /app/rag-service/storage \
    /app/rag-service/.cache/huggingface \
    /app/rag-service/.cache/matplotlib \
    && chown -R ${APP_UID}:${APP_GID} /app/rag-service

USER ${APP_UID}:${APP_GID}

EXPOSE 8020

HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8020/health', timeout=5).read()"

CMD ["python3", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8020"]
