# Surgical Instrument — backend image.
#
# Runs the Phase 3 Flask server (backend.main_server) with a first-boot
# bootstrap that fetches CVC-ColonDB (manual-drop), trains YOLO11n on the
# host's Intel Arc iGPU via torch+xpu, exports to OpenVINO IR, then streams
# annotated frames over /api/video_feed.
#
# The host mounts /dev/dri (and /dev/accel for NPU, optional). Container
# just needs libze1 for level-zero GPU discovery.

FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System deps: OpenCV runtime libs, level-zero for GPU, curl for HEALTHCHECK.
RUN apt-get update && apt-get install -y --no-install-recommends \
      libglib2.0-0 \
      libgl1 \
      libsm6 \
      libxext6 \
      libxrender1 \
      libxcb1 \
      libze1 \
      curl \
      ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# torch + torchvision XPU wheels (Intel Arc iGPU) — installed from Intel's
# index BEFORE the rest of the requirements, so ultralytics doesn't pull the
# CPU-only torch as a dependency.
RUN pip install \
      torch==2.7.1 \
      torchvision==0.22.1 \
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

CMD ["python", "-m", "backend.main_server"]
