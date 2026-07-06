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

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
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
RUN pip install \
      torch==2.12.1 \
      torchvision==0.27.1 \
      --index-url https://download.pytorch.org/whl/xpu

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install -r /app/backend/requirements.txt

# Application code.
COPY backend/ /app/backend/

# Container-side paths. Override from compose to bind-mount host dirs.
ENV BACKEND_CONFIG=/app/backend/config/model.yaml \
    MODELS_DIR=/models \
    DATASETS_DIR=/datasets \
    VIDEOS_DIR=/videos \
    CACHE_DIR=/cache \
    HOST=0.0.0.0 \
    PORT=5001

EXPOSE 5001

# First-boot may train for 20-35 min on Arc iGPU. `start_period` in compose
# swallows that window; here we keep it long as a safety net for `docker run`.
HEALTHCHECK --interval=30s --timeout=10s --start-period=45m --retries=3 \
    CMD curl -fsS http://localhost:5001/api/readiness || exit 1

CMD ["python3", "-m", "backend.main_server"]
