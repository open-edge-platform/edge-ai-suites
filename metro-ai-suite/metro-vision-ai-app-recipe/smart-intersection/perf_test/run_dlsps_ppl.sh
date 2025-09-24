#!/bin/bash

VIDEOS_DIR=./src/dlstreamer-pipeline-server/videos
MODELS_DIR=./src/dlstreamer-pipeline-server/models
OUTPUT_DIR=./perf_test/output

mkdir -p ${OUTPUT_DIR}
chmod o+rwx ${OUTPUT_DIR}

echo "ROOT_DIR=$(pwd)" > perf_test/.env
docker compose -f perf_test/docker-compose.yml up -d --force-recreate --remove-orphans
