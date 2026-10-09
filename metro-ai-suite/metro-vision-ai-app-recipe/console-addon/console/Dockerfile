# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends openssl curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY *.py /app/
COPY templates /app/templates
COPY static /app/static
COPY entrypoint.sh /app/entrypoint.sh
RUN mkdir -p /app/certs && chmod +x /app/entrypoint.sh

RUN useradd -r -u 10001 -m console && chown -R console:console /app
USER console

ENTRYPOINT ["/app/entrypoint.sh"]
