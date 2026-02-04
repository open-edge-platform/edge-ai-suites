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

RUN apt-get update && apt-get install -y \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY src/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy proto and regenerate
COPY proto/*.proto ./proto/
RUN cd proto && \
    python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. --pyi_out=. pose.proto && \
    sed -i 's/^import pose_pb2/from . import pose_pb2/' pose_pb2_grpc.py && \
    touch __init__.py

# Add proto to Python path
ENV PYTHONPATH="${PYTHONPATH}:/app/proto"

# Copy application source
COPY src/*.py ./

# Models and videos are provided at runtime via shared volumes

# Set default environment variables to match shared asset paths
ENV VIDEO_FILE=/videos/3d-pose/face-demographics-walking.mp4
ENV MODEL_PATH=/models/3d-pose/human-pose-estimation-3d-0001.xml
ENV AGGREGATOR_ADDRESS=localhost:50051
ENV SOURCE_ID=3d-pose-camera-1
ENV DEVICE=CPU

CMD python app.py \
    --model ${MODEL_PATH} \
    --video ${VIDEO_FILE} \
    --aggregator ${AGGREGATOR_ADDRESS} \
    --source-id ${SOURCE_ID} \
    --device ${DEVICE}