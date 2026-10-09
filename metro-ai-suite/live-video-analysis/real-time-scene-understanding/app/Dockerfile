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

ARG COPYLEFT_SOURCES=false
COPY scripts/collect_copyleft_python_sources.py /tmp/collect_copyleft_python_sources.py
COPY scripts/build_copyleft_media.sh /tmp/build_copyleft_media.sh
RUN mkdir -p /copyleft_sources/python /copyleft_sources/native /opt/ffmpeg

# Build the pinned FFmpeg/x264 stack and verify its archived source checksums.
RUN if [ "$COPYLEFT_SOURCES" = "true" ]; then \
        bash /tmp/build_copyleft_media.sh && \
        cd /copyleft_sources/native/sources && sha256sum --check SHA256SUMS; \
    fi

# Build PyAV against that stack and assert the expected codec set is present.
RUN if [ "$COPYLEFT_SOURCES" = "true" ]; then \
        cd /copyleft_sources/python/sources && sha256sum --check SHA256SUMS && \
        uv venv /opt/pyav-build && \
        uv pip install --python /opt/pyav-build/bin/python \
            pip==26.2.1 setuptools==80.9.0 Cython==3.1.3 && \
        mkdir -p /tmp/pyav-wheelhouse && \
        PKG_CONFIG_PATH=/opt/ffmpeg/lib/pkgconfig \
        LD_LIBRARY_PATH=/opt/ffmpeg/lib \
            /opt/pyav-build/bin/python -m pip wheel \
                --no-build-isolation --no-deps \
                --wheel-dir /tmp/pyav-wheelhouse \
                /copyleft_sources/python/sources/av-18.1.0.tar.gz && \
        uv pip uninstall --python /opt/venv/bin/python av && \
        uv pip install --python /opt/venv/bin/python --no-deps \
            /tmp/pyav-wheelhouse/av-18.1.0-*.whl && \
        LD_LIBRARY_PATH=/opt/ffmpeg/lib /opt/venv/bin/python -c \
            'import av; assert av.Codec("libx264", "w").name == "libx264"; print(av.library_versions)' && \
        if find /opt/ffmpeg/lib -maxdepth 1 -name 'libx265.so*' -print -quit | grep -q .; then \
            echo "Unexpected x265 library in the controlled FFmpeg build" >&2; exit 1; \
        fi; \
    fi

# Archive the native build recipe and collect sources for copyleft Python packages.
RUN if [ "$COPYLEFT_SOURCES" = "true" ]; then \
        cp /tmp/build_copyleft_media.sh /copyleft_sources/native/sources/build_copyleft_media.sh && \
        (cd /copyleft_sources/native/sources && sha256sum build_copyleft_media.sh >> SHA256SUMS) && \
    /opt/venv/bin/python /tmp/collect_copyleft_python_sources.py > /copyleft_sources/python/copyleft_python_requirements.txt && \
        if [ -s /copyleft_sources/python/copyleft_python_requirements.txt ]; then \
            pip3 download --disable-pip-version-check --no-deps --no-binary=:all: \
                --dest /copyleft_sources/python \
                --requirement /copyleft_sources/python/copyleft_python_requirements.txt; \
        fi; \
    fi

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
    PATH="/opt/venv/bin:$PATH" \
    LD_LIBRARY_PATH="/opt/ffmpeg/lib"

# Virtual environment with installed dependencies.
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /opt/ffmpeg /opt/ffmpeg
COPY --from=builder /copyleft_sources/python /copyleft_sources/python
COPY --from=builder /copyleft_sources/native /copyleft_sources/native

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
        if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
            sed -Ei 's/^Types: deb$/Types: deb deb-src/' /etc/apt/sources.list.d/debian.sources; \
        elif [ -f /etc/apt/sources.list ]; then \
            sed -Ei 's/# deb-src /deb-src /' /etc/apt/sources.list; \
        else \
            echo "Could not find an APT sources file to enable deb-src" >&2; exit 1; \
        fi && \
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
