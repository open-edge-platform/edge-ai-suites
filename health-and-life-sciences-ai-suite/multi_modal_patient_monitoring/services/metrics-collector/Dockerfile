FROM intel/retail-benchmark:3.3.1

ARG HTTP_PROXY

# Optional: Set APT proxy if provided at build time
RUN if [ -n "$HTTP_PROXY" ]; then \
	echo "Acquire::http::Proxy \"$HTTP_PROXY\";" > /etc/apt/apt.conf; \
	fi

WORKDIR /app

# Ensure Python runtime is available for the API
RUN apt-get update && \
	DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends python3 && \
	rm -rf /var/lib/apt/lists/*

COPY app.py ./app.py
COPY start.sh /start.sh
RUN chmod +x /start.sh

EXPOSE 9000

# Run the existing metrics collectors (via supervisord in the base image)
# and the FastAPI app in a single container.
CMD ["/start.sh"]
