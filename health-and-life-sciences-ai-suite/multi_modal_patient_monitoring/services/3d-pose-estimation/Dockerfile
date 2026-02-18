FROM python:3.12-slim

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY


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

EXPOSE 8083 8085

# Remove --device-config argument since app.py no longer supports it
CMD python app.py \
    --model ${MODEL_PATH} \
    --video ${VIDEO_FILE} \
    --aggregator ${AGGREGATOR_ADDRESS} \
    --source-id ${SOURCE_ID}