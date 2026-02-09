FROM python:3.12-slim

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ARG http_proxy
ARG https_proxy
ARG no_proxy

ENV http_proxy=${http_proxy:-$HTTP_PROXY} \
    https_proxy=${https_proxy:-$HTTPS_PROXY} \
    no_proxy=${no_proxy:-$NO_PROXY}

# GPU driver setup
ARG INSTALL_DRIVER_VERSION="25.31.34666"
ARG USER_ID=1000
ARG USER_GROUP_ID=1000

RUN groupadd -g ${USER_GROUP_ID} appuser && useradd -m -s /bin/bash -u ${USER_ID} -g ${USER_GROUP_ID} appuser

# Install system dependencies including Intel GPU drivers
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    libsm6 libxext6 libxrender1 libgomp1 \
    libnuma1 ocl-icd-libopencl1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy GPU driver script from the correct location (relative to build context)
COPY src/tmp/scripts/intel_gpu_drivers.sh /tmp/install_gpu_drivers.sh
RUN chmod +x /tmp/install_gpu_drivers.sh && \
    INSTALL_DRIVER_VERSION=$INSTALL_DRIVER_VERSION /tmp/install_gpu_drivers.sh && \
    rm -rf /tmp/install_gpu_drivers.sh /var/lib/apt/lists/* /tmp/* /root/.cache

WORKDIR /app

# Copy requirements and install Python dependencies (relative to build context)
COPY src/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy proto files and generate Python code (relative to build context)
COPY proto/ ./proto/
RUN cd proto && \
    python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. --pyi_out=. pose.proto && \
    sed -i 's/^import pose_pb2/from . import pose_pb2/' pose_pb2_grpc.py && \
    touch __init__.py

# Copy application source files (relative to build context)
COPY src/*.py ./

ENV PYTHONPATH="${PYTHONPATH}:/app:/app/proto"

# Set default environment variables for GPU operation
ENV VIDEO_FILE=/videos/3d-pose/face-demographics-walking.mp4
ENV MODEL_PATH=/models/3d-pose/human-pose-estimation-3d-0001.xml
ENV AGGREGATOR_ADDRESS=localhost:50051
ENV SOURCE_ID=3d-pose-camera-1
ENV DEPLOYMENT_ENV=production
ENV POSE_3D_DEVICE=GPU

EXPOSE 8083

# Remove --device-config argument since app.py no longer supports it
CMD python app.py \
    --model ${MODEL_PATH} \
    --video ${VIDEO_FILE} \
    --aggregator ${AGGREGATOR_ADDRESS} \
    --source-id ${SOURCE_ID}