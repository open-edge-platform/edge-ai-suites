FROM python:3.11-slim

WORKDIR /app

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HTTP_PROXY=${HTTP_PROXY}
ENV HTTPS_PROXY=${HTTPS_PROXY}
ENV NO_PROXY=${NO_PROXY}

# Runtime deps needed by TensorFlow/OpenVINO wheels.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgl1 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libstdc++6 \
 && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    'pyyaml>=6.0.0' \
    'openvino>=2024.0.0' \
    'tensorflow-cpu==2.16.1'

COPY scripts/convert_rppg_model.py /app/scripts/convert_rppg_model.py

ENTRYPOINT ["python", "/app/scripts/convert_rppg_model.py", "--config", "/app/configs/model-config.yaml"]
