# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

FROM python:3.13-slim

RUN apt-get update && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends \
    ffmpeg \
    gosu \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip setuptools wheel

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY static/ static/

# Create a non-root user (uid 1000) and transfer ownership of /app to it.
RUN useradd -r -u 1000 -g root -d /app app \
    && chown -R app:root /app

# Set HOME so Whisper resolves its cache to /app/.cache/whisper.
ENV HOME=/app

# Pre-cache the Whisper model as the app user so startup is instant.
# NOTE: when a bind mount is used for /app/.cache/whisper the image-layer cache
# is shadowed; the entrypoint script fixes ownership so the app user can write.
ARG WHISPER_MODEL=base
ENV WHISPER_MODEL=${WHISPER_MODEL}
RUN gosu app python -c "from faster_whisper import WhisperModel; WhisperModel('${WHISPER_MODEL}', device='cpu', compute_type='int8')"

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 5000

# Entrypoint runs as root, fixes bind-mount ownership, then exec's as app user.
ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "app.py"]
