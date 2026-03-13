FROM intel/retail-benchmark:3.3.2

ARG HTTP_PROXY

WORKDIR /app

# Ensure Python runtime is available for the API
RUN apt-get update && \
	DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends python3 && \
	rm -rf /var/lib/apt/lists/*

COPY app.py ./app.py
COPY start.sh /start.sh
RUN chmod +x /start.sh

EXPOSE 9001

# Run the existing metrics collectors (via supervisord in the base image)
# and the FastAPI app in a single container.
CMD ["/start.sh"]