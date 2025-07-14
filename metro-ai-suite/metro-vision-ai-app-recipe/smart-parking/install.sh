#!/bin/bash -e

docker run --rm --user=root \
  -e http_proxy -e https_proxy -e no_proxy \
  -v "$(dirname "$(readlink -f "$0")"):/opt/project" \
  openvino/ubuntu22_dev:2024.6.0 bash -c "$(cat <<EOF

cd /opt/project
export HOST_IP="${1:-$(hostname -I | cut -f1 -d' ')}"
echo "Configuring application to use \$HOST_IP"

# shellcheck disable=SC1091
. ./update_dashboard.sh \$HOST_IP

##############################################################################
# 4. Process YOLO model (if any)
##############################################################################
mkdir -p src/dlstreamer-pipeline-server/models/public
YOLO_MODELS=(
    yolov10s
)
download_script="\$(
  curl -L -o - 'https://raw.githubusercontent.com/dlstreamer/dlstreamer/refs/tags/v2025.0.1.3/samples/download_public_models.sh'
)"
for model in \${YOLO_MODELS[@]}; do
    if [ ! -e "src/dlstreamer-pipeline-server/models/public/\$model" ]; then
      bash -c "\$(cat <<EOF2
MODELS_PATH=src/dlstreamer-pipeline-server/models
set -- \$model

\$download_script
EOF2
)"
    fi
done

##############################################################################
# Download and setup videos
##############################################################################
mkdir -p src/dlstreamer-pipeline-server/videos
declare -A video_urls=(
    ["new_video_1.mp4"]="https://github.com/intel/metro-ai-suite/raw/refs/heads/videos/videos/smart_parking_720p_1.mp4"
    ["new_video_2.mp4"]="https://github.com/intel/metro-ai-suite/raw/refs/heads/videos/videos/smart_parking_720p_2.mp4"
    ["new_video_3.mp4"]="https://github.com/intel/metro-ai-suite/raw/refs/heads/videos/videos/smart_parking_720p_3.mp4"
    ["new_video_4.mp4"]="https://github.com/intel/metro-ai-suite/raw/refs/heads/videos/videos/smart_parking_720p_4.mp4"
)
for video_name in "\${!video_urls[@]}"; do
    if [ ! -f src/dlstreamer-pipeline-server/videos/\${video_name} ]; then
        echo "Download \${video_name}..."
        curl -L "\${video_urls[\$video_name]}" -o "src/dlstreamer-pipeline-server/videos/\${video_name}"
    fi
done

echo "Fix ownership..."
chown -R "$(id -u):$(id -g)" src/dlstreamer-pipeline-server/models src/dlstreamer-pipeline-server/videos 2>/dev/null || true
EOF

)"

