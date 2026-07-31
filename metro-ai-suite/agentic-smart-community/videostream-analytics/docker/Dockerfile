# NPU-capable image. Base is ubuntu:24.04 (noble) — NOT python:3.11-slim — because
# the Intel NPU user-space stack (level-zero + NPU driver) ships as Ubuntu 24.04
# packages built against glibc 2.39; they will not install on Debian bookworm slim.
# The container user-space driver must match the HOST kernel intel_vpu driver, at
# version 1.28.0.20251218-20347000698 (Panther Lake / NPU5, device 8086:b03e).
#
# Two package sources — mirroring how the host is set up (verified via apt-cache policy):
#   * level-zero loader (libze1, libze-intel-gpu1)  -> ppa:kobuk-team/intel-graphics
#   * intel-level-zero-npu + intel-driver-compiler-npu -> NOT in any apt repo; they are
#     released as .deb inside a tarball on github.com/intel/linux-npu-driver/releases.
# The NPU compiler (VCL) is bundled inside OpenVINO 2026.x itself, so we do NOT depend
# on the OEM driver's compiler — but the level-zero loader + intel-level-zero-npu are
# still required for device access. Firmware is loaded by the host kernel, so
# intel-fw-npu is intentionally NOT installed here.
FROM ubuntu:24.04

WORKDIR /app

# Proxy for apt/pip/curl (passed via docker compose build-args)
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ENV http_proxy=${HTTP_PROXY} https_proxy=${HTTPS_PROXY} no_proxy=${NO_PROXY}
ENV DEBIAN_FRONTEND=noninteractive

# Keep these in lockstep with the HOST intel_vpu / user-space driver (dpkg -l | grep npu).
# The tarball asset is named linux-npu-driver-<VERSION>-ubuntu2404.tar.gz under tag <TAG>.
ARG NPU_RELEASE_TAG=v1.28.0
ARG NPU_DRIVER_VERSION=1.28.0.20251218-20347000698

# Base deps + level-zero loader from the Intel graphics PPA.
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-venv python3-pip \
        libglib2.0-0 libsm6 libxext6 libxrender1 libgl1 ffmpeg \
        software-properties-common gpg-agent ca-certificates curl \
    && add-apt-repository -y ppa:kobuk-team/intel-graphics \
    && apt-get update \
    && apt-get install -y --no-install-recommends libze1 libze-intel-gpu1 \
    && rm -rf /var/lib/apt/lists/*

# NPU user-space driver from the linux-npu-driver GitHub release tarball. `apt-get
# install ./file.deb` (not dpkg -i) so libze1 and other deps resolve automatically.
# The *-dbgsym.ddeb / *.asc siblings in the tarball are ignored by the *_amd64.deb glob.
# NOTE the asset filename carries a literal "v" before the version:
#   linux-npu-driver-v<VERSION>-ubuntu2404.tar.gz
RUN curl -fsSL -o /tmp/npu.tgz \
        "https://github.com/intel/linux-npu-driver/releases/download/${NPU_RELEASE_TAG}/linux-npu-driver-v${NPU_DRIVER_VERSION}-ubuntu2404.tar.gz" \
    && mkdir -p /tmp/npu && tar xzf /tmp/npu.tgz -C /tmp/npu \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        /tmp/npu/intel-driver-compiler-npu_*_amd64.deb \
        /tmp/npu/intel-level-zero-npu_*_amd64.deb \
    && rm -rf /tmp/npu /tmp/npu.tgz /var/lib/apt/lists/*

# App lives in an isolated venv (Ubuntu 24.04 enforces PEP 668 externally-managed).
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv "$VIRTUAL_ENV"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

COPY pyproject.toml .
COPY shared/ shared/
COPY sinks/ sinks/
COPY stream_monitor/ stream_monitor/
COPY cli.py service.py source_worker.py __init__.py __main__.py ./
RUN pip install --no-cache-dir ".[npu]"

COPY config/ config/

EXPOSE 8999

# Use the installed console script (validates the entry point resolves).
CMD ["videostream-analytics", "serve", "--config", "config/config.yaml"]
