#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY fusion.py .

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Expose any necessary ports (if needed for debugging/monitoring)
EXPOSE 8080

ARG TIMESERIES_UID
ARG TIMESERIES_USER_NAME

RUN groupadd $TIMESERIES_USER_NAME -g $TIMESERIES_UID && \
    useradd -r -u $TIMESERIES_UID -g $TIMESERIES_USER_NAME $TIMESERIES_USER_NAME

USER $TIMESERIES_USER_NAME

# Run the fusion service
CMD ["python", "fusion.py"]
