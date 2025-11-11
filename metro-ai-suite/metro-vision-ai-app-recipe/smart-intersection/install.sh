#!/bin/bash -e

docker run --rm -t \
    -e http_proxy -e https_proxy -e no_proxy \
    -v $(pwd)/init.sh:/init.sh \
    -v $(pwd)/chart:/chart \
    -v $(pwd)/src:/src \
    docker.io/library/python:3.12 bash init.sh

sudo chown -R $USER:$USER src/secrets

mkdir -p src/nginx/ssl
cd src/nginx/ssl
if [ ! -f server.key ] || [ ! -f server.crt ]; then
    echo "Generate self-signed certificate..."
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout server.key -out server.crt -subj "/C=US/ST=CA/L=San Francisco/O=Intel/OU=Edge AI/CN=localhost"
    chown -R "$(id -u):$(id -g)" server.key server.crt 2>/dev/null || true

fi
