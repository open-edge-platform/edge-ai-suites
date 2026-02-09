
FROM python:3.10-slim

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

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


COPY . .


EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
