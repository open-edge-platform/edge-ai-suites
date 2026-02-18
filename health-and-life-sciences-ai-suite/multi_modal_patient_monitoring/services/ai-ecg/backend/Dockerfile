
FROM python:3.12-slim

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

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

# Intel NPU user-space drivers (linux-npu-driver + Level Zero)
COPY ./scripts/install_ubuntu_npu_drivers.sh /tmp/install_npu_drivers.sh
RUN chmod +x /tmp/install_npu_drivers.sh
RUN /tmp/install_npu_drivers.sh

RUN apt-get clean && rm -rf /tmp/install_gpu_drivers.sh /tmp/install_npu_drivers.sh && rm -rf /var/lib/apt/lists/* && rm -rf /tmp/* && rm -rf /root/.cachetmp/*

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