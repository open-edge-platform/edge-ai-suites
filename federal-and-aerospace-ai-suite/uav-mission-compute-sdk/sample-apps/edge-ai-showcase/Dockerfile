# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

FROM python:3.11-slim

# Proxy configuration for Intel network
ARG http_proxy
ARG https_proxy
ARG no_proxy
ENV http_proxy=${http_proxy}
ENV https_proxy=${https_proxy}
ENV no_proxy=${no_proxy}

WORKDIR /app

RUN pip install --no-cache-dir \
    flask==3.1.3 \
    flask-sock==0.7.0 \
    paho-mqtt==2.1.0 \
    requests==2.34.2

COPY app.py .
COPY templates templates/

EXPOSE 5002

CMD ["python", "app.py"]
