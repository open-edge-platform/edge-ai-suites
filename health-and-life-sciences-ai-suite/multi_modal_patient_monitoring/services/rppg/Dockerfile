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
# --------------------------------------
# libglib2.0-0: GLib library (required by OpenCV)
# libsm6, libxext6, libxrender-dev: X11 libraries (for image display support)
# libgomp1: OpenMP library (for parallel processing)
# libgl1-mesa-glx: OpenGL library (for GPU acceleration)
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy and install Python dependencies
# -------------------------------------
# Copy requirements first (Docker layer caching optimization)
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

RUN apt-get clean && rm -rf /tmp/install_gpu_drivers.sh && rm -rf /var/lib/apt/lists/* && rm -rf /tmp/* && rm -rf /root/.cachetmp/*


# Copy proto definition
# ---------------------
COPY proto/ ./proto/

# Generate gRPC Python code from proto
# -------------------------------------
# This creates vital_pb2.py and vital_pb2_grpc.py in src/
RUN python -m grpc_tools.protoc \
    -I./proto \
    --python_out=./src \
    --grpc_python_out=./src \
    ./proto/vital.proto

# Copy application code
# ---------------------
COPY src/ ./src/
COPY config.yaml .

# Create runtime directories
# --------------------------
RUN mkdir -p models videos cache logs

# Set Python path so imports work
ENV PYTHONPATH=/app

# Expose gRPC port
EXPOSE 5004

# Health check (optional but recommended)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import grpc; channel = grpc.insecure_channel('localhost:5004'); channel.close()" || exit 1

# Run service
CMD ["python", "-m", "src.app"]
