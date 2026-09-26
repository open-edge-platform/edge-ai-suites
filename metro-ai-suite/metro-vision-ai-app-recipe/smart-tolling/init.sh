#!/bin/bash

SOURCE="src"
CHART="chart"
if [ ! -f "${SOURCE}/secrets/browser.auth" ]; then
  bash ${SOURCE}/secrets/generate_secrets.sh
fi

if [ ! -f .env ]; then
  touch .env
fi

USER_UID=$(stat -c '%u' "${SOURCE}"/* | sort -rn | head -1)
USER_GID=$(stat -c '%g' "${SOURCE}"/* | sort -rn | head -1)

echo "UID=$USER_UID" > .env
echo "GID=$USER_GID" >> .env

if [ ! -d "${SOURCE}/dlstreamer-pipeline-server/videos" ] || [ -z "$(find "${SOURCE}/dlstreamer-pipeline-server/videos" -type f -name "*.ts" 2>/dev/null)" ]; then
  VIDEO_BRANCH="main"
  VIDEO_URL="https://github.com/open-edge-platform/edge-ai-resources/raw/refs/heads/${VIDEO_BRANCH}/videos"
  VIDEOS=("1122east_h264.ts" "1122west_h264.ts" "1122north_h264.ts" "1122south_h264.ts")
  VIDEO_DIR="${SOURCE}/dlstreamer-pipeline-server/videos"

  mkdir -p "${VIDEO_DIR}"
  
  echo "Downloading videos in parallel..."
  for VIDEO in "${VIDEOS[@]}"; do
    curl -k -L -s "${VIDEO_URL}/${VIDEO}" -o "${VIDEO_DIR}/${VIDEO}" &
  done
  
  # # Dummy download to potentially improve bandwidth allocation
  # curl -k -L -s "${VIDEO_URL}/LICENSE" -o "${VIDEO_DIR}/LICENSE" &
  
  wait
  
  for VIDEO in "${VIDEOS[@]}"; do
    if [ ! -f "${VIDEO_DIR}/${VIDEO}" ]; then
        echo "Error: Failed to download ${VIDEO}"
        exit 1
    fi
  done
fi

# Copy files to chart
mkdir -p ${CHART}/files
mkdir -p ${CHART}/files/dlstreamer-pipeline-server/user_scripts/gvapython/sscape
mkdir -p ${CHART}/files/webserver
cp -r \
  ${SOURCE}/controller \
  ${SOURCE}/grafana \
  ${SOURCE}/mosquitto \
  ${SOURCE}/node-red \
  ${CHART}/files
cp -r \
  ${SOURCE}/dlstreamer-pipeline-server/user_scripts \
  ${CHART}/files/dlstreamer-pipeline-server
cp \
  ${SOURCE}/dlstreamer-pipeline-server/config.json \
  ${CHART}/files/dlstreamer-pipeline-server/config.json
cp \
  ${SOURCE}/webserver/user_access_config.json \
  ${CHART}/files/webserver/user_access_config.json
