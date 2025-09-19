#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
FROM python:3.13.4-slim

WORKDIR /app
COPY opcua-server/requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

ARG TIMESERIES_UID
ARG TIMESERIES_USER_NAME
RUN groupadd $TIMESERIES_USER_NAME -g $TIMESERIES_UID && \
    useradd -r -u $TIMESERIES_UID -g $TIMESERIES_USER_NAME $TIMESERIES_USER_NAME

# Build arg to optionally download sources of all deb and python packages with MPL, GPL, EPL, CDDL, LGPL licenses
ARG COPYLEFT_SOURCES=false

RUN if [ "$COPYLEFT_SOURCES" = "true" ]; then \
    mkdir -p /app/python-licenses && \
    cd /app/python-licenses && \
    apt-get update && apt-get install -y --no-install-recommends gcc build-essential libffi-dev && \
    apt-get clean && rm -rf /var/lib/apt/lists/* && \
    pip3 freeze | cut -d= -f1 | while read pkg; do \
      meta=$(pip3 show $pkg 2>/dev/null); \
      lic=$(echo "$meta" | grep -i '^License:' | grep -Ei 'MPL|GPL|General Public License|EPL|Eclipse Public License|CDDL|LGPL'); \
      if [ ! -z "$lic" ]; then \
        echo "Downloading source for $pkg with license: $lic"; \
        pip3 download --no-binary :all: $pkg || true; \
      fi; \
    done; \
      apt-get remove --purge -y gcc build-essential libffi-dev; \
    fi

WORKDIR /app
COPY opcua-server/opcua_server.py .

RUN apt-get remove --purge -y --allow-remove-essential perl-base

USER ${TIMESERIES_USER_NAME}
HEALTHCHECK --interval=5m CMD exit 0

ENTRYPOINT ["python3", "opcua_server.py"]
