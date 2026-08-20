# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

# Topic Extractor — subscribes to MQTT uav telemetry and writes time-series
# measurements to InfluxDB for post-flight analysis and Grafana dashboards.

FROM python:3.11-slim

ARG http_proxy
ARG https_proxy
ARG no_proxy
ENV http_proxy=${http_proxy} https_proxy=${https_proxy} no_proxy=${no_proxy}

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ENV http_proxy= https_proxy= no_proxy=

COPY extractor.py .

ENV MQTT_BROKER_HOST=localhost \
    MQTT_BROKER_PORT=1883 \
    UAV_ID= \
    INFLUXDB_URL= \
    INFLUXDB_TOKEN= \
    INFLUXDB_ORG= \
    INFLUXDB_BUCKET= \
    LOG_LEVEL=INFO

CMD ["python", "extractor.py"]
