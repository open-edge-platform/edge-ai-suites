
FROM python:3.12-slim

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

# ----------------------------------------------------------------------------
# System dependencies (OpenVINO + OpenCV GPU requirements)
# ----------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    libgl1 \
    libnuma1 \
    ocl-icd-libopencl1 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ----------------------------------------------------------------------------
# Install Python dependencies
# ----------------------------------------------------------------------------
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ----------------------------------------------------------------------------
# GPU Driver Installation (Same as rppg)
# ----------------------------------------------------------------------------
ARG INSTALL_DRIVER_VERSION="25.31.34666"

COPY scripts/install_ubuntu_gpu_drivers.sh /tmp/install_gpu_drivers.sh
RUN chmod +x /tmp/install_gpu_drivers.sh
RUN /tmp/install_gpu_drivers.sh

RUN apt-get clean && \
    rm -rf /tmp/install_gpu_drivers.sh && \
    rm -rf /var/lib/apt/lists/* && \
    rm -rf /tmp/*

# ----------------------------------------------------------------------------
# Copy application code
# ----------------------------------------------------------------------------
COPY . .

ENV PYTHONPATH=/app

EXPOSE 8000

# ----------------------------------------------------------------------------
# Healthcheck
# ----------------------------------------------------------------------------
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# ----------------------------------------------------------------------------
# Run app
# ----------------------------------------------------------------------------
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
