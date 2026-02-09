# FROM intel/retail-benchmark:3.3.1

# ARG HTTP_PROXY

# # Optional: Set APT proxy if provided at build time
# RUN if [ -n "$HTTP_PROXY" ]; then \
# 	echo "Acquire::http::Proxy \"$HTTP_PROXY\";" > /etc/apt/apt.conf; \
# 	fi

# WORKDIR /app

# # Ensure Python runtime is available for the API
# RUN apt-get update && \
# 	DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends python3 && \
# 	rm -rf /var/lib/apt/lists/*

# COPY app.py ./app.py
# COPY start.sh /start.sh
# RUN chmod +x /start.sh

# EXPOSE 9000

# # Run the existing metrics collectors (via supervisord in the base image)
# # and the FastAPI app in a single container.
# CMD ["/start.sh"]
FROM intel/retail-benchmark:latest

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

# Copy application files
COPY app.py /app/
COPY start.sh /app/

# Make start script executable
RUN chmod +x /app/start.sh

# Expose HTTP API port
EXPOSE 9000

# Start both supervisord (collectors) and HTTP API
CMD ["/app/start.sh"]