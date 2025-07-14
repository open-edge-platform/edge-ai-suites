#!/bin/bash -e

docker run --rm -ti \
    -e http_proxy -e https_proxy -e no_proxy \
    -v $(pwd)/init.sh:/init.sh \
    -v $(pwd)/chart:/chart \
    -v $(pwd)/src:/src \
    docker.io/library/python:3.12 bash init.sh