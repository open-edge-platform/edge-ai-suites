# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

FROM python:3.12-slim

LABEL org.opencontainers.image.title="APM Detection Service"
LABEL org.opencontainers.image.description="Detection-layer orchestration (DL Streamer) for agentic predictive maintenance"
LABEL org.opencontainers.image.vendor="Intel Corporation"

WORKDIR /app

RUN groupadd -r appuser && useradd -r -g appuser -u 1002 appuser

# Intel GPU compute runtime (OpenCL + Level Zero user-mode drivers). Required
# for use cases that run OpenVINO inference on device=GPU directly inside this
# container (e.g. gas-detection-multimodal). Without it OpenVINO's GPU plugin
# can't initialize and only CPU is enumerated. Sourced from the same Intel
# graphics PPA the host uses so the user-mode driver tracks the host kernel
# driver. Set --build-arg INSTALL_GPU_RUNTIME=false to build a CPU-only image.
ARG INSTALL_GPU_RUNTIME=true
COPY intel-graphics.sources /tmp/intel-graphics.sources
RUN if [ "$INSTALL_GPU_RUNTIME" = "true" ]; then \
        set -e; \
        apt-get update && apt-get install -y --no-install-recommends ca-certificates; \
        cp /tmp/intel-graphics.sources /etc/apt/sources.list.d/intel-graphics.sources; \
        apt-get update; \
        apt-get install -y --no-install-recommends \
            intel-opencl-icd \
            libze-intel-gpu1 \
            libze1 \
            ocl-icd-libopencl1; \
        rm -rf /var/lib/apt/lists/*; \
    fi; \
    rm -f /tmp/intel-graphics.sources

# Intel NPU user-mode driver (Level Zero NPU + compiler). Required for use
# cases that run OpenVINO inference on device=NPU directly inside this
# container. Not carried by the Intel graphics PPA, so it's installed from the
# intel/linux-npu-driver GitHub release (same build the host uses); libtbb12 is
# a required dependency of intel-driver-compiler-npu. intel-fw-npu is skipped —
# the NPU firmware is loaded by the host kernel, not the container. Set
# --build-arg INSTALL_NPU_RUNTIME=false to build without NPU support.
ARG INSTALL_NPU_RUNTIME=true
ARG NPU_DRIVER_VERSION=v1.35.0
ARG NPU_DRIVER_TARBALL=linux-npu-driver-v1.35.0.20260722-29947505341-ubuntu2404.tar.gz
RUN if [ "$INSTALL_NPU_RUNTIME" = "true" ]; then \
        set -e; \
        apt-get update; \
        apt-get install -y --no-install-recommends ca-certificates wget libtbb12; \
        cd /tmp; \
        wget -q "https://github.com/intel/linux-npu-driver/releases/download/${NPU_DRIVER_VERSION}/${NPU_DRIVER_TARBALL}" -O npu.tar.gz; \
        mkdir -p npu && tar -xf npu.tar.gz -C npu; \
        dpkg -i $(find npu -name 'intel-level-zero-npu*.deb') $(find npu -name 'intel-driver-compiler-npu*.deb'); \
        rm -rf /tmp/npu /tmp/npu.tar.gz /var/lib/apt/lists/*; \
    fi

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

# Third-party notices for the Python packages installed above
COPY third_party_programs.txt /licenses/third_party_programs.txt

# Optionally fetch source for any copyleft-licensed dependency (deb or pip) so
# it can be redistributed alongside the image for license compliance. Off by
# default; set --build-arg COPYLEFT_SOURCES=true to enable.
ARG COPYLEFT_SOURCES=false
RUN if [ "$COPYLEFT_SOURCES" = "true" ]; then \
        set -e; \
        # Debian trixie's deb822 sources format ships with source repos disabled
        sed -i 's/^Types: deb$/Types: deb deb-src/' /etc/apt/sources.list.d/*.sources 2>/dev/null || true; \
        apt-get update && \
        mkdir -p /copyleft_sources/deb && cd /copyleft_sources/deb && \
        : > copyleft_package_list.txt && \
        for package in $(dpkg -l | awk '/^ii/ {print $2}' | cut -d: -f1); do \
            if [ -f "/usr/share/doc/${package}/copyright" ] && \
               grep -lqE 'Copyleft|GPL|LGPL|EPL|MPL|CDDL' "/usr/share/doc/${package}/copyright"; then \
                echo "${package}" >> copyleft_package_list.txt; \
                apt-get source -q --download-only "${package}" || true; \
            fi; \
        done; \
        # Get source for installed Python packages under copyleft licenses
        mkdir -p /copyleft_sources/python && cd /copyleft_sources/python && \
        apt-get install -y --no-install-recommends gcc build-essential libffi-dev python3-dev && \
        pip list --format=freeze | cut -d= -f1 | while read -r pkg; do \
            meta=$(pip show "$pkg" 2>/dev/null); \
            lic=$(echo "$meta" | grep -i '^License:' | grep -E 'MPL|GPL|General Public License|EPL|Eclipse Public License|CDDL|LGPL'); \
            if [ -n "$lic" ]; then \
                echo "Downloading source for $pkg with license: $lic"; \
                pip download --no-cache-dir --no-binary :all: --no-deps "$pkg" || true; \
            fi; \
        done; \
        apt-get remove --purge -y gcc build-essential libffi-dev python3-dev && \
        rm -rf /var/lib/apt/lists/*; \
    fi

RUN mkdir -p /app/videos && chown -R appuser:appuser /app

USER appuser

EXPOSE 5004

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "5004", "--workers", "1"]
