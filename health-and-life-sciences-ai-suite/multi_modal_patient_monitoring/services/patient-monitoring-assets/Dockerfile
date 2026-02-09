########################################
# Builder stage: download & convert assets
########################################
FROM python:3.11-slim AS builder

# ----------------------------
# Optional proxy support
# ----------------------------
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ARG http_proxy
ARG https_proxy
ARG no_proxy

ENV http_proxy=${http_proxy:-$HTTP_PROXY} \
    https_proxy=${https_proxy:-$HTTPS_PROXY} \
    no_proxy=${no_proxy:-$NO_PROXY} \
    HTTP_PROXY=${HTTP_PROXY:-$http_proxy} \
    HTTPS_PROXY=${HTTPS_PROXY:-$https_proxy} \
    NO_PROXY=${NO_PROXY:-$no_proxy}

# ----------------------------
# System deps (minimal)
# ----------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    wget \
    git \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ----------------------------
# Python deps for asset generation
# ----------------------------
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# ----------------------------
# App scripts used to build assets
# ----------------------------
COPY scripts/ /app/scripts/
RUN chmod +x /app/scripts/*.sh

# ----------------------------
# Build assets at image build time
# ----------------------------
RUN mkdir -p /models /videos && \
    echo '[INFO] (builder) Downloading rPPG assets...' && \
    python /app/scripts/rppg_download_assets.py && \
    echo '[INFO] (builder) Downloading 3D pose assets via OMZ script...' && \
    python /app/scripts/3d_pose_model_convert.py && \
    echo '[INFO] (builder) Downloading ECG assets...' && \
    /app/scripts/ecg_download_assets.sh && \
    echo '[INFO] (builder) All asset downloads complete.'


########################################
# Final stage: slim runtime image
########################################
FROM python:3.11-slim

# ----------------------------
# Optional proxy support
# ----------------------------
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ARG http_proxy
ARG https_proxy
ARG no_proxy

ENV http_proxy=${http_proxy:-$HTTP_PROXY} \
    https_proxy=${https_proxy:-$HTTPS_PROXY} \
    no_proxy=${no_proxy:-$NO_PROXY} \
    HTTP_PROXY=${HTTP_PROXY:-$http_proxy} \
    HTTPS_PROXY=${HTTPS_PROXY:-$https_proxy} \
    NO_PROXY=${NO_PROXY:-$no_proxy}

WORKDIR /app

# Minimal system deps (no heavy ML frameworks here)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Copy prebuilt assets from builder image
COPY --from=builder /models /opt/assets/models
COPY --from=builder /videos /opt/assets/videos

# Shared asset volumes (host-mapped by docker-compose)
VOLUME ["/models", "/videos"]

# ----------------------------
# Default command: copy assets into volumes and exit
# ----------------------------
CMD ["sh", "-c", "\
    echo '[INFO] Copying prebuilt patient monitoring assets into mounted volumes...' && \
    mkdir -p /models /videos && \
    cp -r /opt/assets/models/. /models/ && \
    cp -r /opt/assets/videos/. /videos/ && \
    echo '[INFO] All asset copies complete. Exiting container.'\
"]

