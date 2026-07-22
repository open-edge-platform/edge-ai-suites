# Surgical Instrument — backend image.
#
# Runs the Phase 3 Flask server (backend.main_server) with a first-boot
# bootstrap that fetches CVC-ColonDB (manual-drop), trains YOLO11n on the
# host's Intel Arc / Xe iGPU via torch+xpu, exports to OpenVINO IR, then
# streams annotated frames over /api/video_feed.
#
# The host mounts /dev/dri (and /dev/accel for NPU, optional). The container
# needs the Intel graphics compute runtime (Level Zero GPU/NPU drivers +
# OpenCL ICD) — installed from Intel's official Ubuntu 24.04 repo. Without
# these, torch.xpu.device_count() returns 0 even when /dev/dri is mounted
# and the process is in the render group.

FROM ubuntu:24.04

# Proxy support for corporate networks. Build args are optional; if not
# supplied, defaults to empty (no proxy). Pass via docker build --build-arg
# or docker-compose build args.
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

WORKDIR /app

ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY} \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_BREAK_SYSTEM_PACKAGES=1 \
    DEBIAN_FRONTEND=noninteractive

# Base runtime: Python + OpenCV shared libs + curl for HEALTHCHECK.
# The Intel graphics userspace (libze-intel-gpu, intel-opencl-icd, level-zero
# NPU driver) is installed from Intel's compute-runtime repo below — this is
# what the DL Streamer pipeline container also uses.
RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 \
      python3-pip \
      python3-venv \
      libglib2.0-0 \
      libgl1 \
      libsm6 \
      libxext6 \
      libxrender1 \
      libxcb1 \
      curl \
      wget \
      gnupg \
      gpg-agent \
      ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN wget -qO - https://repositories.intel.com/gpu/intel-graphics.key \
      | gpg --dearmor -o /usr/share/keyrings/intel-graphics.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/intel-graphics.gpg] https://repositories.intel.com/gpu/ubuntu noble unified" \
      > /etc/apt/sources.list.d/intel-gpu-noble.list \
    && apt-get update && apt-get install -y --no-install-recommends \
      libze1 \
      libze-intel-gpu1 \
      intel-opencl-icd \
      intel-media-va-driver-non-free \
    && rm -rf /var/lib/apt/lists/*

# torch + torchvision XPU wheels (Intel iGPU / Arc / Xe) — installed from
# Intel's PyPI index BEFORE the rest of the requirements so ultralytics
# doesn't pull the CPU-only torch as a dependency.
#
# Version pin matches the poc/gabriel_test/.venv setup that trained YOLO11n
# on MTL's Arc iGPU end-to-end in ~21 minutes for 50 epochs. torch 2.7.x
# had immature SYCL kernels for YOLO's loss / target-assignment ops and
# stalls indefinitely inside get_assigned_targets_and_loss on Xe3.
#
# We install the torch/torchvision wheels by direct URL from
# download.pytorch.org (rather than from --index-url) because pip's index
# resolution redirects wheel downloads through the Cloudflare R2 mirror
# (download-r2.pytorch.org), whose TLS handshake is rejected by our
# corporate proxy. The two large wheels are still served from S3 by the
# primary host directly and succeed via the proxy.
#
# --no-deps + explicit dep install below because triton-xpu==3.7.1 is
# ONLY served from the R2 mirror (S3 direct returns AccessDenied). We
# skip triton-xpu entirely — it's used exclusively by torch.compile,
# which Ultralytics YOLO training does not invoke.
RUN pip install \
      --retries 8 \
      --timeout 120 \
      --no-deps \
      "https://download.pytorch.org/whl/xpu/torch-2.12.1%2Bxpu-cp312-cp312-linux_x86_64.whl" \
      "https://download.pytorch.org/whl/xpu/torchvision-0.27.1%2Bxpu-cp312-cp312-manylinux_2_28_x86_64.whl" \
 && pip install \
      --retries 8 \
      --timeout 120 \
      "filelock>=3.13" \
      "typing-extensions>=4.10" \
      "sympy>=1.13.3" \
      "networkx>=3.0" \
      "jinja2>=3.1" \
      "fsspec>=2024.2.0" \
      "pyyaml>=6.0" \
      "intel-pti==0.16.0" \
      "intel-cmplr-lib-rt==2025.3.2" \
      "intel-cmplr-lib-ur==2025.3.2" \
      "intel-cmplr-lic-rt==2025.3.2" \
      "intel-sycl-rt==2025.3.2" \
      "intel-opencl-rt==2025.3.2" \
      "intel-openmp==2025.3.2" \
      "dpcpp-cpp-rt==2025.3.2" \
      "mkl==2025.3.1" \
      "onemkl-license==2025.3.1" \
      "onemkl-sycl-blas==2025.3.1" \
      "onemkl-sycl-dft==2025.3.1" \
      "onemkl-sycl-lapack==2025.3.1" \
      "onemkl-sycl-rng==2025.3.1" \
      "onemkl-sycl-sparse==2025.3.1" \
      "tbb==2022.3.1" \
      "tcmlib==1.4.1" \
      "umf==1.0.3" \
      "oneccl==2021.17.2" \
      "oneccl-devel==2021.17.2" \
      "impi-rt==2021.17.2"

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install -r /app/backend/requirements.txt

# Re-pin torch+xpu after requirements.txt runs. Ultralytics 8.4.75's
# transitive resolution pulls torch 2.12.1+cu130 from PyPI (CUDA build)
# and silently replaces our XPU wheel. We force-reinstall the XPU wheel
# by direct URL, --no-deps so no other package gets touched.
RUN pip install \
      --retries 8 \
      --timeout 120 \
      --no-deps \
      --force-reinstall \
      "https://download.pytorch.org/whl/xpu/torch-2.12.1%2Bxpu-cp312-cp312-linux_x86_64.whl" \
      "https://download.pytorch.org/whl/xpu/torchvision-0.27.1%2Bxpu-cp312-cp312-manylinux_2_28_x86_64.whl"

# Application code.
COPY backend/ /app/backend/

# ---------------------------------------------------------------------------
# Slice E: Basler USB3 camera enumeration.
# Intentionally placed AFTER the (expensive) torch+xpu install and the
# `COPY backend/` step so tweaks to this layer never invalidate the multi-
# gigabyte torch cache. `pypylon` bundles the pylon USB3 runtime; libusb
# is the only apt dep the wheel needs. Actual USB access is granted at
# `docker run` time via the /dev/bus/usb passthrough that `make up` wires
# in when it detects a Basler vendor ID 2676 on the host.
# ---------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
      libusb-1.0-0 \
 && rm -rf /var/lib/apt/lists/* \
 && pip install --retries 4 --timeout 60 pypylon==4.0.0

# Container-side paths. Override from compose to bind-mount host dirs.
ENV BACKEND_CONFIG=/app/backend/config/model.yaml \
    MODELS_DIR=/models \
    DATASETS_DIR=/datasets \
    VIDEOS_DIR=/videos \
    CACHE_DIR=/cache \
    HOST=0.0.0.0 \
    PORT=5001 \
    LD_LIBRARY_PATH=/usr/local/lib:/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH}

EXPOSE 5001

# First-boot may train for 20-35 min on Arc iGPU. `start_period` in compose
# swallows that window; here we keep it long as a safety net for `docker run`.
HEALTHCHECK --interval=30s --timeout=10s --start-period=45m --retries=3 \
    CMD curl -fsS http://localhost:5001/api/readiness || exit 1

CMD ["python3", "-m", "backend.main_server"]
