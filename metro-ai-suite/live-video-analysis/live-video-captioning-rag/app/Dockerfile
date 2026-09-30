# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

FROM python:3.12-slim AS base

# Install GPU drivers
# Copy drivers and set execute permission on sh files
ARG INSTALL_DRIVER_VERSION="26.18.38308"
COPY ./drivers/install_gpu_drivers.sh /tmp/drivers/install_gpu_drivers.sh
RUN chmod +x /tmp/drivers/install_gpu_drivers.sh

RUN echo "Installing GPU drivers version $INSTALL_DRIVER_VERSION" && \
    apt-get update && apt-get install -y --no-install-recommends ca-certificates libxml2 && \
    python -m pip install --upgrade --no-cache-dir pip==26.1.2 && \
    /tmp/drivers/install_gpu_drivers.sh && \
    apt-get clean && rm -rf /tmp/drivers /var/lib/apt/lists/* /tmp/*

# Install the Intel NPU user-space stack: the NPU
# driver/compiler/firmware plus the oneAPI Level Zero loader (libze1). The
# loader is mandatory — without libze_loader.so.1 the NPU plugin cannot
# enumerate the device. The final test fails the build if it is missing.
ARG NPU_DRIVER_VERSION="1.35.0"
ARG NPU_DRIVER_BUILD="v1.35.0.20260722-29947505341-ubuntu2404"
ARG LEVEL_ZERO_VERSION="1.28.2-1~24.04~ppa1"
ARG LEVEL_ZERO_PPA_SNAPSHOT="20260606T100000Z"

RUN mkdir -p /tmp/npu_deps && cd /tmp/npu_deps \
    && apt-get update && apt-get install -y --no-install-recommends curl ca-certificates libtbb12 \
    && curl -L --retry 5 --retry-delay 5 --retry-all-errors -O https://github.com/intel/linux-npu-driver/releases/download/v${NPU_DRIVER_VERSION}/linux-npu-driver-${NPU_DRIVER_BUILD}.tar.gz \
    && tar -xf linux-npu-driver-${NPU_DRIVER_BUILD}.tar.gz \
    && curl -L --retry 5 --retry-delay 5 --retry-all-errors -O https://snapshot.ppa.launchpadcontent.net/kobuk-team/intel-graphics/ubuntu/${LEVEL_ZERO_PPA_SNAPSHOT}/pool/main/l/level-zero-loader/libze1_${LEVEL_ZERO_VERSION}_amd64.deb \
    && dpkg -i ./*.deb \
    && ldconfig \
    && test -e /usr/lib/x86_64-linux-gnu/libze_loader.so.1 \
    && apt-get purge -y curl && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /tmp/npu_deps /var/lib/apt/lists/*

# Build stage
FROM base AS builder

# Install system dependencies
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install --no-cache-dir uv==0.11.10

# Set working directory
WORKDIR /app

# COPY dependencies packages list and lock file
COPY pyproject.toml uv.lock ./

# Install dependencies to a virtual environment
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV UV_PROJECT_ENVIRONMENT="/opt/venv"
RUN uv sync --frozen --no-dev --no-install-project

# Download Chart.js during build for airgapped runtime
RUN mkdir -p ui/js/vendor && \
    curl -o ui/js/vendor/chart.js https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js

# Production stage
FROM base AS production

RUN apt-get update && apt-get upgrade -y && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/opt/venv/bin:$PATH"

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Set working directory and change ownership
WORKDIR /app

# Copy application code
COPY --chown=appuser:appuser main.py ./
COPY --chown=appuser:appuser backend ./backend
COPY --chown=appuser:appuser ui ./ui

# Copy Chart.js from builder stage
COPY --from=builder --chown=appuser:appuser /app/ui/js/vendor/chart.js ./ui/js/vendor/chart.js

# Optionally download copyleft sources if requested
ARG COPYLEFT_SOURCES=false
RUN if [ "$COPYLEFT_SOURCES" = "true" ]; then \
    echo "Installing COPYLEFT SOURCES" && \
    apt-get update && \
    # Get list of installed deb packages with copyleft licenses \
    sed -Ei 's/# deb-src /deb-src /' /etc/apt/sources.list && \
    apt-get update && \
    mkdir -p /copyleft_sources/deb && cd /copyleft_sources/deb && \
    echo -n $null > copyleft_package_list.txt && \
    for package in $(dpkg -l | awk '/^ii/ {print $2}' | cut -d: -f1); do \
    grep -l 'Copyleft\|GPL\|LGPL\|EPL\|MPL\|CDDL' /usr/share/doc/${package}/copyright; \
    exit_status=$?; \
    if [ $exit_status -eq 0 ]; then \
    echo $package >> copyleft_package_list.txt; \
    apt-get source -q --download-only $package; \
    fi; \
    done; \
    # Get source code for installed Python packages with copyleft licenses \
    mkdir -p /copyleft_sources/python && \
    cd /copyleft_sources/python && \
    apt-get update && apt-get install -y --no-install-recommends gcc build-essential libffi-dev python3-dev && \
    # Download python package sources with relevant licenses \
    pip3 freeze | cut -d= -f1 | while read pkg; do \
    meta=$(pip3 show $pkg 2>/dev/null); \
    lic=$(echo "$meta" | grep -i '^License:' | grep -E 'MPL|GPL|General Public License|EPL|Eclipse Public License|CDDL|LGPL'); \
    if [ ! -z "$lic" ]; then \
    echo "Downloading source for $pkg with license: $lic"; \
    pip3 download --no-binary :all: $pkg || true; \
    fi; \
    done; \
    apt-get remove --purge -y gcc build-essential libffi-dev python3-dev; \
    fi

# Switch to non-root user
USER appuser

EXPOSE 4172

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "4172"]
