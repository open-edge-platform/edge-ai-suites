FROM intel/retail-benchmark:3.3.1


# Use proxy only temporarily for apt (if provided)
RUN if [ -n "$HTTP_PROXY" ]; then \
        echo "Acquire::http::Proxy \"$HTTP_PROXY\";" > /etc/apt/apt.conf; \
    fi && \
    apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends python3 && \
    rm -rf /var/lib/apt/lists/* && \
    rm -f /etc/apt/apt.conf

# Explicitly clear any inherited proxy ENV (safety step)
ENV http_proxy= \
    https_proxy= \
    HTTP_PROXY= \
    HTTPS_PROXY= \
    no_proxy= \
    NO_PROXY=

WORKDIR /app

COPY app.py ./app.py
COPY start.sh /start.sh
RUN chmod +x /start.sh

EXPOSE 9001

CMD ["/start.sh"]