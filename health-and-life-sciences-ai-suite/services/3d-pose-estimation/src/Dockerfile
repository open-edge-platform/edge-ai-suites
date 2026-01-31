FROM python:3.12-slim

ENV http_proxy=http://proxy-mu.intel.com:911
ENV https_proxy=http://proxy-mu.intel.com:911
ENV HTTP_PROXY=http://proxy-mu.intel.com:911
ENV HTTPS_PROXY=http://proxy-mu.intel.com:911
ENV no_proxy=localhost,127.0.0.0/8,::1,.intel.com,.intel.net,localhost

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

# Copy models and videos
COPY models ./models
COPY videos ./videos

# Set environment variables
ENV VIDEO_FILE=/app/videos/face-demographics-walking.mp4
ENV MODEL_PATH=/app/models/human-pose-estimation-3d-0001.xml
ENV AGGREGATOR_ADDRESS=localhost:50051
ENV SOURCE_ID=3d-pose-camera-1
ENV DEVICE=CPU

CMD python app.py \
    --model ${MODEL_PATH} \
    --video ${VIDEO_FILE} \
    --aggregator ${AGGREGATOR_ADDRESS} \
    --source-id ${SOURCE_ID} \
    --device ${DEVICE}