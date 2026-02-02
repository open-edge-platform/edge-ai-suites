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
# Set working directory inside the container
WORKDIR /app

# Install system packages (if grpcio needs build tools on some platforms)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies definition
COPY requirements.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application source and proto package (including *_pb2*.py stubs)
COPY aggregator ./aggregator
COPY proto ./proto

# Expose gRPC port
EXPOSE 50051

# Start the aggregator gRPC server as a module so top-level stubs are importable
CMD ["python", "-m", "aggregator.server"]
