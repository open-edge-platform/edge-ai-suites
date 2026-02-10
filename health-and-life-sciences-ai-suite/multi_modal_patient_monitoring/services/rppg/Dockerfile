# ============================================================================
# RPPG Service Dockerfile
# ============================================================================
# Multi-stage build for production-ready container

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
# Install system dependencies for OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*


WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# GPU support (if using OpenVINO with GPU plugin, ensure the base image has necessary drivers/libraries)
ARG INSTALL_DRIVER_VERSION="25.31.34666"
ARG USER_ID=1000
ARG USER_GROUP_ID=1000

RUN groupadd -g ${USER_GROUP_ID} appuser && useradd -m -s /bin/bash -u ${USER_ID} -g ${USER_GROUP_ID} appuser

RUN apt-get update -y && apt-get install -y --no-install-recommends --fix-missing \
    curl \
    && rm -rf /var/lib/apt/lists/* 

COPY ./scripts/install_ubuntu_gpu_drivers.sh /tmp/install_gpu_drivers.sh
RUN chmod +x /tmp/install_gpu_drivers.sh
RUN /tmp/install_gpu_drivers.sh

# Intel NPU user-space drivers (linux-npu-driver + Level Zero)
COPY ./scripts/install_ubuntu_npu_drivers.sh /tmp/install_npu_drivers.sh
RUN chmod +x /tmp/install_npu_drivers.sh
RUN /tmp/install_npu_drivers.sh

RUN apt-get clean && rm -rf /tmp/install_gpu_drivers.sh /tmp/install_npu_drivers.sh && rm -rf /var/lib/apt/lists/* && rm -rf /tmp/* && rm -rf /root/.cachetmp/*

# Copy proto definition
COPY proto/ ./proto/


# Copy application code
COPY src/ ./src/
COPY config.yaml .

# Copy pre-downloaded assets (if present) into the image
#COPY models/ ./models/
#COPY videos/ ./videos/

# Create runtime directories (ensure they exist even if empty on host)
RUN mkdir -p models videos cache logs

ENV PYTHONPATH=/app

EXPOSE 5004

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import grpc; channel = grpc.insecure_channel('localhost:5004'); channel.close()" || exit 1

CMD ["python", "-m", "src.app"]