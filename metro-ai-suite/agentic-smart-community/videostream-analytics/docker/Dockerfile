# GPU + NPU capable image, multi-stage on Debian (python:3.13-slim, currently
# trixie). Inference devices CPU / GPU (iGPU) / NPU are all usable; the device is
# picked in config/config.yaml. Requires compose to pass through /dev/dri (iGPU)
# and /dev/accel/accel0 (NPU).
# NOTE: the NPU/GPU driver debs need glibc >= 2.38, i.e. trixie or newer. If the
# build fails on libc6 version conflicts, purge stale cached python:3.13-slim
# images (pre-2025-08 tags were bookworm) and rebuild.
#
# Stage layout — build-only tooling (curl, compilers, pip caches) never reaches
# the shipped image, which keeps trivy findings on the final stage minimal:
#   python-base    common base shared by all stages
#   builder-base   python venv with the app + openvino[npu]; also downloads the
#                  NPU driver debs (linux-npu-driver release), the libze1 deb
#                  (kobuk PPA snapshot, direct deb URL) and the iGPU compute
#                  runtime debs (intel/compute-runtime + IGC releases)
#   ffmpeg-builder ffmpeg from the official ffmpeg.org tarball (pinned
#                  FFMPEG_VERSION, dlstreamer fedora41 pattern). Debian's stock
#                  ffmpeg deb drags in ~35 unused libraries — each a trivy
#                  finding with no Debian patch. The tarball doubles as the
#                  copyleft source shipped in /copyleft_sources.
#   runtime        final image: Debian runtime libs + copyleft sources + NPU/ZE/
#                  GPU debs + venv + app config. curl is kept for the compose
#                  healthcheck and in-container debugging.
#
# Firmware (NPU) is loaded by the host kernel, so intel-fw-npu is intentionally
# NOT installed here.

FROM python:3.13-slim AS python-base
ENV DEBIAN_FRONTEND=noninteractive

# Security updates first: Docker Hub's official slim images lag the Debian
# repos, so preinstalled base-layer packages (e.g. util-linux 2.41-5) can carry
# CVEs that already have fixes in trixie (e.g. 2.41.5-0+deb13u1). Doing this in
# python-base makes every stage below inherit the patched packages.
RUN apt-get update -y && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
FROM python-base AS builder-base

WORKDIR /app

# curl here is for the downloads below; the runtime stage installs its own
# copy for the compose healthcheck.
RUN apt-get update -y && apt-get install --no-install-recommends -y \
        curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# NPU user-space driver debs — keep in lockstep with the HOST intel_vpu driver
# (dpkg -l | grep npu). Asset name carries a literal "v" before the version.
ARG NPU_RELEASE_TAG=v1.28.0
ARG NPU_DRIVER_VERSION=1.28.0.20251218-20347000698
RUN curl -fsSL --retry 5 --retry-delay 5 --retry-all-errors -o /tmp/npu.tgz \
        "https://github.com/intel/linux-npu-driver/releases/download/${NPU_RELEASE_TAG}/linux-npu-driver-v${NPU_DRIVER_VERSION}-ubuntu2404.tar.gz" \
    && mkdir -p /tmp/npu /npu-debs \
    && tar xzf /tmp/npu.tgz -C /tmp/npu \
    && find /tmp/npu \( -name 'intel-driver-compiler-npu_*_amd64.deb' \
                    -o -name 'intel-level-zero-npu_*_amd64.deb' \) \
           -exec mv {} /npu-debs/ \; \
    && rm -rf /tmp/npu /tmp/npu.tgz

# Level-zero loader (libze1) deb, pinned version + PPA snapshot timestamp —
# the exact package the host runs (ppa:kobuk-team/intel-graphics). Direct deb
# URL, so no Ubuntu-only add-apt-repository is needed.
ARG LEVEL_ZERO_VERSION=1.28.2-1~24.04~ppa1
ARG LEVEL_ZERO_PPA_SNAPSHOT=20260606T100000Z
RUN mkdir -p /ze \
    && curl -fsSL --retry 5 --retry-delay 5 --retry-all-errors \
        -o "/ze/libze1_${LEVEL_ZERO_VERSION}_amd64.deb" \
        "https://snapshot.ppa.launchpadcontent.net/kobuk-team/intel-graphics/ubuntu/${LEVEL_ZERO_PPA_SNAPSHOT}/pool/main/l/level-zero-loader/libze1_${LEVEL_ZERO_VERSION}_amd64.deb"

# iGPU user-space stack (level-zero GPU backend + OpenCL ICD + IGC + GmmLib) for
# OpenVINO device "GPU". Deb set mirrors the "26.18.38308" case of the company
# standard install_ubuntu_gpu_drivers.sh (vlm-openvino-serving); the debs are
# apt-installed in the runtime stage instead of the script's dpkg -i.
ARG GPU_DRIVER_VERSION=26.18.38308
RUN mkdir -p /gpu-debs && cd /gpu-debs \
    && curl -fsSL --retry 5 --retry-delay 5 --retry-all-errors -O \
        https://github.com/intel/compute-runtime/releases/download/26.18.38308.1/libze-intel-gpu1_26.18.38308.1-0_amd64.deb \
    && curl -fsSL --retry 5 --retry-delay 5 --retry-all-errors -O \
        https://github.com/intel/compute-runtime/releases/download/26.18.38308.1/intel-opencl-icd_26.18.38308.1-0_amd64.deb \
    && curl -fsSL --retry 5 --retry-delay 5 --retry-all-errors -O \
        https://github.com/intel/compute-runtime/releases/download/26.18.38308.1/libigdgmm12_22.10.0_amd64.deb \
    && curl -fsSL --retry 5 --retry-delay 5 --retry-all-errors -O \
        https://github.com/intel/compute-runtime/releases/download/26.18.38308.1/intel-ocloc_26.18.38308.1-0_amd64.deb \
    && curl -fsSL --retry 5 --retry-delay 5 --retry-all-errors -O \
        https://github.com/intel/intel-graphics-compiler/releases/download/v2.34.4/intel-igc-core-2_2.34.4+21428_amd64.deb \
    && curl -fsSL --retry 5 --retry-delay 5 --retry-all-errors -O \
        https://github.com/intel/intel-graphics-compiler/releases/download/v2.34.4/intel-igc-opencl-2_2.34.4+21428_amd64.deb

# App venv, carried over to the runtime stage unchanged. Upgrade pip first so
# the shipped venv has the latest pip.
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv "$VIRTUAL_ENV"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip

COPY pyproject.toml .
COPY shared/ shared/
COPY sinks/ sinks/
COPY stream_monitor/ stream_monitor/
COPY cli.py service.py source_worker.py __init__.py __main__.py ./
RUN pip install --no-cache-dir ".[npu]"

# ---------------------------------------------------------------------------
# ffmpeg from the official GitHub mirror tag tarball (dlstreamer fedora41
# pattern; ffmpeg.org itself is unreachable through some corporate proxies, so
# the mirror is used unconditionally — same source, tag n<version>).
# Debian's stock ffmpeg deb drags in ~35 unused libraries, each a trivy finding
# with no Debian patch. The tarball doubles as the copyleft source shipped in
# the final image. Build tools never leave this stage.
FROM python-base AS ffmpeg-builder
ARG FFMPEG_VERSION=7.1.5
RUN apt-get update -y && apt-get install --no-install-recommends -y \
        build-essential pkg-config nasm libx264-dev curl ca-certificates \
    && mkdir -p "/src/ffmpeg/ffmpeg-${FFMPEG_VERSION}" /copyleft_sources/deb \
    && curl -fsSL --retry 5 --retry-delay 5 --retry-all-errors \
        -o "/copyleft_sources/ffmpeg-${FFMPEG_VERSION}.tar.gz" \
        "https://github.com/FFmpeg/FFmpeg/archive/refs/tags/n${FFMPEG_VERSION}.tar.gz" \
    && tar -xf "/copyleft_sources/ffmpeg-${FFMPEG_VERSION}.tar.gz" \
        -C "/src/ffmpeg/ffmpeg-${FFMPEG_VERSION}" --strip-components=1 \
    && sed -Ei "s/Types: deb/Types: deb deb-src/g" /etc/apt/sources.list.d/debian.sources \
    && apt-get update -y \
    && cd /copyleft_sources/deb \
    && apt-get source --no-install-recommends -q --download-only x264 \
    && rm -rf /var/lib/apt/lists/*

# --enable-libx264: the app re-encodes clips to browser-compatible H.264
# (roi_processor.py / roi.py).
# --enable-network: REQUIRED by the continuous recorder's default "copy"
# backend, which pulls RTSP itself (`ffmpeg -rtsp_transport tcp -c copy -f
# segment`) instead of decoding through OpenCV — see stream_monitor/
# continuous_recorder.py. Without it the rtsp demuxer is compiled out
# entirely and every recording session dies with "Protocol not found".
# No TLS library is linked, so https/rtmps stay unavailable; a protocol
# whitelist is deliberately NOT used because configure's
# rtsp_demuxer_select pulls http_protocol back in regardless.
# --disable-ffprobe: nothing shells out to ffprobe (the recorder reads
# durations from ffmpeg's own segment list). Static libav* -> single binary;
# only runtime dependency is libx264-164.
RUN cd "/src/ffmpeg/ffmpeg-${FFMPEG_VERSION}" \
    && ./configure \
        --disable-doc --disable-debug --enable-network \
        --disable-ffplay --disable-ffprobe \
        --enable-pic --enable-static --disable-shared \
        --enable-gpl --enable-libx264 \
        --extra-libs=-lpthread --extra-libs=-lm \
    && make -j"$(nproc)" ffmpeg \
    && install -m 755 ffmpeg /usr/local/bin/ffmpeg

# Build-time capability assertion: a network-less ffmpeg still builds and runs
# fine, it just fails at the first recording session in production. Fail the
# BUILD instead (same intent as the gst engine's gst-inspect assertions).
RUN set -eu; \
    ff=/usr/local/bin/ffmpeg; \
    "$ff" -hide_banner -formats 2>/dev/null | grep -qE '^ *D[E ]? *rtsp( |$)' \
        || { echo "MISSING: ffmpeg rtsp demuxer (--enable-network?)"; exit 1; }; \
    for proto in file pipe tcp rtp; do \
        "$ff" -hide_banner -protocols 2>/dev/null | grep -qE "^ *${proto}\$" \
            || { echo "MISSING: ffmpeg protocol ${proto}"; exit 1; }; \
    done; \
    "$ff" -hide_banner -h encoder=libx264 2>/dev/null | grep -q '^Encoder libx264' \
        || { echo "MISSING: ffmpeg libx264 encoder"; exit 1; }; \
    echo "ffmpeg capabilities OK (rtsp demuxer + file/pipe/tcp/rtp + libx264)"

# ---------------------------------------------------------------------------
FROM python-base AS runtime

# Runtime libraries only. opencv-python-headless and OpenVINO link against NONE
# of the usual opencv-era X/glib libs (verified via ldd), so libglib2.0/libsm6/
# libxext6/libxrender1/libgl1 are NOT installed. libx264-164: ffmpeg's only dep.
# libnuma1 + ocl-icd-libopencl1: iGPU compute runtime deps.
# curl: used by the compose healthcheck and for in-container debugging.
RUN apt-get update -y && apt-get install --no-install-recommends -y \
        libx264-164 \
        libnuma1 \
        ocl-icd-libopencl1 \
        ca-certificates \
        curl

# ffmpeg binary + its copyleft sources (upstream tarball + x264 source).
COPY --from=ffmpeg-builder /usr/local/bin/ffmpeg /usr/local/bin/ffmpeg
COPY --from=ffmpeg-builder /copyleft_sources /copyleft_sources

# Level-zero loader + NPU driver + iGPU compute runtime. `apt-get install
# ./file.deb` (not dpkg -i) so libtbb12 etc. resolve from the repos.
COPY --from=builder-base /ze /tmp/ze
COPY --from=builder-base /npu-debs /tmp/npu-debs
COPY --from=builder-base /gpu-debs /tmp/gpu-debs
RUN apt-get install -y --no-install-recommends \
        /tmp/ze/libze1_*_amd64.deb \
        /tmp/npu-debs/intel-driver-compiler-npu_*_amd64.deb \
        /tmp/npu-debs/intel-level-zero-npu_*_amd64.deb \
        /tmp/gpu-debs/*.deb \
    && ldconfig \
    && test -e /usr/lib/x86_64-linux-gnu/libze_loader.so.1 \
    && test -e /usr/lib/x86_64-linux-gnu/libze_intel_gpu.so.1 \
    && rm -rf /tmp/ze /tmp/npu-debs /tmp/gpu-debs /var/lib/apt/lists/*

# Prebuilt venv from the builder stage.
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
COPY --from=builder-base /opt/venv /opt/venv

# Optionally download copyleft sources for ALL installed copyleft packages. The self-built ffmpeg +
# x264 sources are ALWAYS shipped (see ffmpeg-builder) because ffmpeg is not a
# deb here and this scan would miss it. Build with:
#   docker build --build-arg COPYLEFT_SOURCES=true ...
ARG COPYLEFT_SOURCES=false
RUN if [ "$COPYLEFT_SOURCES" = "true" ]; then \
        sed -Ei "s/Types: deb/Types: deb deb-src/g" /etc/apt/sources.list.d/debian.sources && \
        apt-get update && \
        cd /copyleft_sources/deb && \
        for package in $(dpkg -l | awk '/^ii/ {print $2}' | cut -d: -f1); do \
            if grep -q 'Copyleft\|GPL\|LGPL\|EPL\|MPL\|CDDL' /usr/share/doc/${package}/copyright 2>/dev/null; then \
                echo $package >> copyleft_package_list.txt; \
                apt-get source -q --download-only $package || true; \
            fi; \
        done; \
        mkdir -p /copyleft_sources/python && cd /copyleft_sources/python && \
        apt-get install --no-install-recommends -y gcc build-essential libffi-dev python3-dev && \
        "$VIRTUAL_ENV/bin/pip" freeze | cut -d= -f1 | while read pkg; do \
            meta=$("$VIRTUAL_ENV/bin/pip" show $pkg 2>/dev/null); \
            lic=$(echo "$meta" | grep -i '^License:' | grep -E 'MPL|GPL|General Public License|EPL|Eclipse Public License|CDDL|LGPL'); \
            if [ ! -z "$lic" ]; then \
                echo "Downloading source for $pkg with license: $lic"; \
                "$VIRTUAL_ENV/bin/pip" download --no-binary :all: $pkg || true; \
            fi; \
        done; \
        apt-get purge -y gcc build-essential libffi-dev python3-dev && \
        apt-get autoremove -y && apt-get clean && rm -rf /var/lib/apt/lists/*; \
    fi

# Hardening, last layer: perl-base and pip are both unused at runtime.
# perl-base carries unfixed CRITICAL CVEs and nothing installed rdepends on it
# (verified via apt-get -s purge); it is marked Essential, hence
# --allow-remove-essential — safe here because this is the final layer.
# pip is only needed at build time; its vendored msgpack/setuptools have no
# fixed pip release yet. pip remains available in the builder stage.
RUN apt-get purge -y --allow-remove-essential perl-base \
    && apt-get clean && rm -rf /var/lib/apt/lists/* \
    && rm -rf /opt/venv/lib/python3*/site-packages/pip* \
              /opt/venv/bin/pip* \
              /usr/local/lib/python3*/site-packages/pip* \
              /usr/local/lib/python3*/ensurepip \
              /usr/local/bin/pip*

# The package itself is installed into the venv site-packages; only the runtime
# config needs to live in /app (compose bind-mounts over config/config.yaml).
WORKDIR /app
COPY config/ config/

RUN groupadd appuser \
    && useradd -m -s /bin/bash -g appuser appuser
USER appuser

EXPOSE 8999

# Use the installed console script (validates the entry point resolves).
CMD ["videostream-analytics", "serve", "--config", "config/config.yaml"]
