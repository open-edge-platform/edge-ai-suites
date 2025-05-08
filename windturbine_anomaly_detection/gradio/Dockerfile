#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

FROM python:3.13.2-slim
# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive

ARG TIMESERIES_UID
ARG TIMESERIES_USER_NAME
RUN groupadd $TIMESERIES_USER_NAME -g $TIMESERIES_UID && \
    useradd -r -u $TIMESERIES_UID -g $TIMESERIES_USER_NAME $TIMESERIES_USER_NAME

# Set the working directory
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

RUN apt-get remove --purge -y --allow-remove-essential perl-base

HEALTHCHECK --interval=5m CMD exit 0

USER $TIMESERIES_USER_NAME
# Set the default command to run your application
CMD ["python3", "app.py"]
