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
RUN pip install --default-timeout=300 --retries 5 --no-cache-dir -r /app/requirements.txt

# ----------------------------
# App scripts used to build assets (model-config.yaml is mounted at runtime)
# ----------------------------
COPY scripts/ /app/scripts/
RUN mkdir -p /app/configs && chmod +x /app/scripts/*.sh

## ----------------------------
## (No asset build at image build time)
## Asset download/conversion is now performed at container startup
## once model-config.yaml is mounted into /app/configs.
## ----------------------------


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


WORKDIR /app

# Minimal system deps (no heavy ML frameworks here)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Reuse Python deps and scripts installed in builder
COPY --from=builder /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app/scripts /app/scripts

# Shared asset volumes (host-mapped by docker-compose)
VOLUME ["/models", "/videos"]

# ----------------------------
# Default command: run asset scripts at startup then exit
# ----------------------------
CMD ["sh", "-c", "\
    echo '[INFO] Running patient monitoring asset preparation scripts at startup...' && \
    mkdir -p /models /videos /app/configs && \
    python /app/scripts/rppg_download_assets.py && \
    python /app/scripts/3d_pose_model_convert.py && \
    python /app/scripts/ecg_download_assets.py && \
    echo '[INFO] Patient monitoring asset preparation complete. Exiting container.'\
"]

