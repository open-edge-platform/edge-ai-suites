#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
FROM python:3.13.2-slim

WORKDIR /app
COPY opcua-server/requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

ARG TIMESERIES_UID
ARG TIMESERIES_USER_NAME
RUN groupadd $TIMESERIES_USER_NAME -g $TIMESERIES_UID && \
    useradd -r -u $TIMESERIES_UID -g $TIMESERIES_USER_NAME $TIMESERIES_USER_NAME

COPY opcua-server/opcua_server.py .
COPY simulation_data/windturbine_data.csv .

RUN apt-get remove --purge -y --allow-remove-essential perl-base

USER ${TIMESERIES_USER_NAME}
HEALTHCHECK --interval=5m CMD exit 0

ENTRYPOINT ["python3", "opcua_server.py"]