FROM python:3.12-slim

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY


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
CMD ["uvicorn", "aggregator.server:app", "--host", "0.0.0.0", "--port", "8001"]
