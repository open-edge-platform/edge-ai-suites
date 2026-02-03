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

# ----------------------------
# System deps (minimal)
# ----------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    wget \
    git \
 && rm -rf /var/lib/apt/lists/*

# ----------------------------
# Python deps
# ----------------------------
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# ----------------------------
# App files
# ----------------------------
WORKDIR /app

# Copy all scripts into /app/scripts
COPY scripts/ /app/scripts/
RUN chmod +x /app/scripts/*.sh

# ----------------------------
# Shared asset volumes
# ----------------------------
VOLUME ["/models", "/videos"]

# ----------------------------
# Default command
# ----------------------------
CMD ["sh", "-c", "\
    echo '[INFO] Downloading rPPG assets...' && \
    python /app/scripts/rppg_download_assets.py && \
    echo '[INFO] Downloading 3D pose assets via OMZ script...' && \
    python /app/scripts/3d_pose_model_convert.py  && \
    echo '[INFO] Downloading ECG assets...' && \
    /app/scripts/ecg_download_assets.sh && \
    echo '[INFO] All asset downloads complete. Exiting container.'\
"]

