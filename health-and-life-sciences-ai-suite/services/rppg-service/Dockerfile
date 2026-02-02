# ============================================================================
# RPPG Service Dockerfile
# ============================================================================
# Multi-stage build for production-ready container

FROM python:3.11-slim

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