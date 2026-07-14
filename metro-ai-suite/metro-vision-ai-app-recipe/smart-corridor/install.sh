#!/bin/bash -e

HOST_IP="${1:-$(hostname -I | cut -f1 -d' ')}"

docker run --rm -t \
    -e http_proxy -e https_proxy -e no_proxy \
    -e HOST_IP="$HOST_IP" \
    -v $(pwd)/init.sh:/init.sh \
    -v $(pwd)/chart:/chart \
    -v $(pwd)/src:/src \
    docker.io/library/python:3.12 bash init.sh

# if ENABLE_TC=true is set, configure TC network settings and create resolv.conf for DNS relay
if [ "${ENABLE_TC}" = "true" ]; then
    ./tc-setup.sh
    docker compose -f ../compose-scenescape.yml -f ../tc-overlay-deps.yml config \
        --no-interpolate --no-normalize --no-path-resolution --no-env-resolution \
        > ../docker-compose.yml
fi

sudo chown -R $USER:$USER src/secrets

# If this is a parent deployment (TOTAL_REMOTE_CHILD set in .env), run CA federation
ENV_FILE="../.env"
if [[ -f "$ENV_FILE" ]]; then
    TOTAL_REMOTE_CHILD=$(grep -E "^TOTAL_REMOTE_CHILD=" "$ENV_FILE" | cut -d'=' -f2 | tr -d '"')
    TOTAL_REMOTE_CHILD=${TOTAL_REMOTE_CHILD:--1}
    if [[ "$TOTAL_REMOTE_CHILD" -gt 0 ]] 2>/dev/null; then
        echo "Parent deployment detected (TOTAL_REMOTE_CHILD=${TOTAL_REMOTE_CHILD})"
        echo "Running CA bundle..."
        bash ./ca-bundle.sh
    elif [[ "$TOTAL_REMOTE_CHILD" -eq 0 ]]; then
        echo "Single Node Parent deployment detected(TOTAL_REMOTE_CHILD=${TOTAL_REMOTE_CHILD})"
        echo "No child deployments — skipping CA bundle"
    else
        # Child deployment: use child appdata and config
        echo "Child deployment detected — using smart-corridor-child-ri.tar.bz2"
        ln -sf smart-corridor-child-ri.tar.bz2 src/webserver/smart-corridor-ri.tar.bz2
        echo "Child deployment detected — using config_child.json"
        ln -sf config_child.json src/dlstreamer-pipeline-server/config.json
    fi
else
    # No .env — default to child
    echo "Error: .env file not found."
    exit 1
fi

mkdir -p src/nginx/ssl
cd src/nginx/ssl
if [ ! -f server.key ] || [ ! -f server.crt ]; then
    echo "Generate self-signed certificate..."
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout server.key -out server.crt -subj "/C=US/ST=CA/L=San Francisco/O=Intel/OU=Edge AI/CN=localhost"
    chown -R "$(id -u):$(id -g)" server.key server.crt 2>/dev/null || true
fi
