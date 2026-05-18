FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# System deps (GPU/NPU drivers added when using an OpenVINO base image)
RUN apt-get update && apt-get install -y --no-install-recommends \
	libglib2.0-0 \
	libgl1 \
	libsm6 \
	libxext6 \
	libxrender1 \
	libxcb1 \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

EXPOSE 5001

CMD ["python", "run_mvp_backend.py", "--config", "configs/mvp-backend.yaml", "--host", "0.0.0.0", "--port", "5001"]
