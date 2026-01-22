FROM python:3.12-slim

ENV http_proxy=http://proxy-mu.intel.com:911
ENV https_proxy=http://proxy-mu.intel.com:911
ENV HTTP_PROXY=http://proxy-mu.intel.com:911
ENV HTTPS_PROXY=http://proxy-mu.intel.com:911
ENV no_proxy=localhost,127.0.0.0/8,::1,.intel.com,.intel.net,localhost
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

# Copy the application source, protobuf stubs, and proto definitions
COPY aggregator ./aggregator
COPY vital_pb2.py vital_pb2_grpc.py ./
COPY proto ./proto

# Expose gRPC port
EXPOSE 50051

# Start the aggregator gRPC server as a module so top-level stubs are importable
CMD ["python", "-m", "aggregator.server"]
