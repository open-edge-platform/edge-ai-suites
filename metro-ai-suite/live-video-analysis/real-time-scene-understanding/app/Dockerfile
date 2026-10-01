# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

FROM python:3.12-slim AS base

# Install GPU drivers.
ARG INSTALL_DRIVER_VERSION="26.18.38308"
COPY scripts/install_ubuntu_gpu_drivers.sh /tmp/drivers/install_gpu_drivers.sh
RUN chmod +x /tmp/drivers/install_gpu_drivers.sh

RUN echo "Installing GPU drivers version $INSTALL_DRIVER_VERSION" \
    && apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl libxml2 \
    && python -m pip install --upgrade --no-cache-dir pip==26.2.1 \
    && /tmp/drivers/install_gpu_drivers.sh \
    && apt-get clean \
    && rm -rf /tmp/drivers /var/lib/apt/lists/* /tmp/*

# Install the Intel NPU user-space stack: the NPU
# driver/compiler/firmware plus the oneAPI Level Zero loader (libze1). The
# loader is mandatory — without libze_loader.so.1 the NPU plugin cannot
# enumerate the device. The final test fails the build if it is missing.
ARG NPU_DRIVER_VERSION="1.35.0"
ARG NPU_DRIVER_BUILD="v1.35.0.20260722-29947505341-ubuntu2404"
ARG LEVEL_ZERO_VERSION="1.28.2-1~24.04~ppa1"
ARG LEVEL_ZERO_PPA_SNAPSHOT="20260606T100000Z"

WORKDIR /tmp/npu_deps
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates libtbb12 \
    && curl -L --retry 5 --retry-delay 5 --retry-all-errors -O https://github.com/intel/linux-npu-driver/releases/download/v${NPU_DRIVER_VERSION}/linux-npu-driver-${NPU_DRIVER_BUILD}.tar.gz \
    && tar -xf linux-npu-driver-${NPU_DRIVER_BUILD}.tar.gz \
    && curl -L --retry 5 --retry-delay 5 --retry-all-errors -O https://snapshot.ppa.launchpadcontent.net/kobuk-team/intel-graphics/ubuntu/${LEVEL_ZERO_PPA_SNAPSHOT}/pool/main/l/level-zero-loader/libze1_${LEVEL_ZERO_VERSION}_amd64.deb \
    && dpkg -i ./*.deb \
    && ldconfig \
    && test -e /usr/lib/x86_64-linux-gnu/libze_loader.so.1 \
    && apt-get purge -y curl && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /tmp/npu_deps /var/lib/apt/lists/*

# Build stage.
FROM base AS builder

# Install system dependencies.
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv.
RUN pip install --no-cache-dir uv==0.11.10

WORKDIR /app

# Copy dependency manifests and install dependencies into a dedicated venv.
COPY pyproject.toml uv.lock ./
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV UV_PROJECT_ENVIRONMENT="/opt/venv"
RUN uv sync --frozen --no-dev --no-install-project

# Production stage.
FROM base AS production

RUN apt-get update && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user used by the app process after entrypoint drops privileges.
RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH="/opt/venv/bin:$PATH"

# Virtual environment with installed dependencies.
COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

# Application source.
COPY --chown=appuser:appuser main.py ./
COPY --chown=appuser:appuser backend/ ./backend/
COPY --chown=appuser:appuser ui/ ./ui/

# Optionally download copyleft sources if requested
ARG COPYLEFT_SOURCES=false
RUN if [ "$COPYLEFT_SOURCES" = "true" ]; then \
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
        apt-get update && apt-get install --no-install-recommends -y gcc build-essential libffi-dev python3-dev && \
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

# The application runs entirely out of /opt/venv (a self-contained venv with
# no pip installed — see `uv sync --no-install-project` in the builder
# stage). The system Python's pip (installed earlier in the `base` stage
# purely to run the GPU driver installer script, and by the COPYLEFT_SOURCES
# block above when enabled) is not needed at runtime, and its bundled/
# vendored copies of setuptools and msgpack only add unmaintained CVE
# surface to the shipped image. Only strip it for the default (non-copyleft)
# build, since the COPYLEFT_SOURCES=true path still needs pip3 during build.
RUN if [ "$COPYLEFT_SOURCES" != "true" ]; then \
        python -m pip uninstall -y pip setuptools wheel 2>/dev/null; \
        rm -rf /usr/local/lib/python3.12/ensurepip \
               /usr/local/lib/python3.12/site-packages/pip* \
               /usr/local/lib/python3.12/site-packages/setuptools* \
               /usr/local/lib/python3.12/site-packages/wheel* \
               /usr/local/lib/python3.12/site-packages/_distutils_hack \
               /usr/local/lib/python3.12/site-packages/distutils-precedence.pth; \
    fi

# Fixes bind-mounted segments-dir ownership at startup, then drops to
# appuser — see entrypoint.sh for why this can't just be USER appuser.
COPY entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh

EXPOSE 9100

ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9100"]
