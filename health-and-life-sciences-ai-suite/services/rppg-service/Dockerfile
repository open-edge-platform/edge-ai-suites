# ============================================================================
# RPPG Service Dockerfile
# ============================================================================
# Multi-stage build for production-ready container

FROM python:3.12-slim
ENV http_proxy=http://proxy-mu.intel.com:911
ENV https_proxy=http://proxy-mu.intel.com:911
ENV HTTP_PROXY=http://proxy-mu.intel.com:911
ENV HTTPS_PROXY=http://proxy-mu.intel.com:911
ENV no_proxy=localhost,127.0.0.0/8,::1,.intel.com,.intel.net,localhost
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
