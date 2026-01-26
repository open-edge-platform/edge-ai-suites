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

# Copy application source
COPY src/ ./

# Copy proto definitions + generated code
COPY proto ./proto

# Copy models and videos
COPY models ./models
COPY videos ./videos

CMD ["python", "app.py"]
